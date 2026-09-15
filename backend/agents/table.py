"""The table agents play at, run like an online game with a clock.

Every phase (movement, retreats, builds and removals alike) is open for at most
`phase_seconds`. It closes early the moment every player with something to order
has submitted. Humans and agents are held to the same clock.

Each agent acts when there is a reason to (the phase opened, a message arrived,
its last submission was refused, time is nearly up, or it has been quiet for a
while) and never more often than once every `min_interval` seconds. A shared
limit caps how many model calls run at once across every game in the process,
so a busy table cannot flood the provider.

An agent's reply may send messages, submit, both, or neither. A submission is
orders plus the commitment sheet plus notes, and is all-or-nothing: one faulty
entry refuses the whole submission, the agent is told exactly why on its next
turn, and it may try again before the deadline.

Every input an agent attempts is stored in agent_actions, one row per message,
order, commitment, submission or unreadable reply, with ok=0 and the reason for
anything faulty. Every model call is stored in agent_calls with its cost.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import asdict
from typing import Awaitable, Callable

import storage
from agents.briefing import briefing, turn_prompt
from agents.models import Call, Model
from engine.facade import POWERS, Facade
from research.chart import parse_chart

MAX_CONCURRENT_CALLS = int(os.environ.get("AGENT_CONCURRENCY", "4"))
_slots: dict[int, asyncio.Semaphore] = {}


def _api_slots() -> asyncio.Semaphore:
    """One limit per event loop (a semaphore cannot cross loops)."""
    loop = asyncio.get_running_loop()
    return _slots.setdefault(id(loop), asyncio.Semaphore(MAX_CONCURRENT_CALLS))


class CostCap(RuntimeError):
    pass


def _json(text: str) -> dict:
    t = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if fence:
        t = fence.group(1)
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("the reply was JSON but not an object")
    return data


class Table:
    def __init__(self, game_id: str, facade: Facade, seats: dict[str, Model], *,
                 resolve: Callable[[], Awaitable[None]], human: str | None = None,
                 phase_seconds: float = 120, min_interval: float = 5.0, idle_after: float = 20.0,
                 final_call: float = 25.0, cost_cap_usd: float = 5.0, characters: bool = False):
        self.game_id, self.f, self.seats, self.human = game_id, facade, seats, human
        self.resolve = resolve
        self.phase_seconds, self.min_interval = phase_seconds, min_interval
        self.idle_after, self.final_call, self.cost_cap = idle_after, final_call, cost_cap_usd
        self.briefings = {p: briefing(p, phase_seconds / 60, characters) for p in seats}
        self.task: asyncio.Task | None = None
        self.phase_done = asyncio.Event()
        self.over_budget = False

    # -------------------------------------------------------------- the clock
    def must_submit(self) -> set[str]:
        return {p for p in POWERS if self.f.legal_orders(p)}

    def waiting_on(self) -> set[str]:
        return self.must_submit() - storage.submitted(self.game_id, self.f.phase)

    def seconds_left(self) -> float:
        d = storage.deadline(self.game_id)
        return 0.0 if d is None else max(0.0, d - time.time())

    def start(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass

    async def run(self) -> None:
        """Play phases until the game ends."""
        while not self.f.done:
            await self.play_phase()

    async def play_phase(self) -> None:
        phase = self.f.phase
        if storage.deadline(self.game_id) is None:        # a restart keeps the deadline it had
            storage.set_deadline(self.game_id, time.time() + self.phase_seconds)
        self.phase_done = asyncio.Event()
        if not self.waiting_on():
            self.phase_done.set()
        agents = [asyncio.create_task(self._agent(p, phase)) for p in self.seats if p != self.human]
        try:
            await asyncio.wait_for(self.phase_done.wait(), timeout=self.seconds_left())
        except asyncio.TimeoutError:
            pass
        for t in agents:
            t.cancel()
        await asyncio.gather(*agents, return_exceptions=True)
        for p in self.waiting_on() & set(self.seats):
            storage.log_action(self.game_id, p, phase, "deadline", {}, False,
                               "the deadline passed before a submission was accepted; units hold")
        storage.set_deadline(self.game_id, None)
        await self.resolve()

    def submitted(self, power: str) -> None:
        """Called for every accepted submission, human or agent."""
        storage.mark_submitted(self.game_id, self.f.phase, power)
        if not self.waiting_on():
            self.phase_done.set()

    # -------------------------------------------------------------- one agent
    async def _agent(self, power: str, phase: str) -> None:
        if not self.f.legal_orders(power):
            return
        last_call = -1e9
        seen = 0
        feedback: list[str] = []
        warned = False
        first = True
        while power in self.waiting_on() and self.f.phase == phase:
            now = time.monotonic()
            left = self.seconds_left()
            inbox = [m for m in storage.messages_for(self.game_id, power)
                     if m["phase"] == phase and m["sender"] != power]
            newest = max((m["id"] for m in inbox), default=0)
            final = left <= self.final_call and not warned
            due = first or newest > seen or feedback or final or now - last_call >= self.idle_after
            if not due or now - last_call < self.min_interval or self.over_budget:
                await asyncio.sleep(min(0.25, self.min_interval / 4))
                continue
            first, seen, last_call = False, newest, now
            warned = warned or final
            feedback = await self._act(power, phase, left, feedback, final)

    async def _act(self, power: str, phase: str, left: float, feedback: list[str], final: bool) -> list[str]:
        waiting = self.waiting_on()
        call = Call(self.briefings[power], turn_prompt(
            power=power, state=self.f.state(power), legal=self.f.legal_orders(power), seconds_left=left,
            submitted=self.must_submit() - waiting, waiting=waiting,
            press=self._visible_press(power), notes=storage.notes_for(self.game_id, power),
            last_result=storage.last_result(self.game_id), feedback=feedback, final_call=final),
            "act", power, self.f.legal_orders(power), [p for p in POWERS if p != power])
        model = self.seats[power]

        if storage.game_cost(self.game_id) >= self.cost_cap:
            self.over_budget = True
            storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, None,
                             f"cost cap ${self.cost_cap:.2f} reached; agents stop acting", {})
            return []
        async with _api_slots():
            try:
                out = await model.complete(call)
            except asyncio.CancelledError:
                storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, None,
                                 "cancelled: the phase closed while the call was in flight", {})
                raise
            except Exception as e:  # noqa: BLE001 -- recorded, never swallowed
                storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, None,
                                 f"{type(e).__name__}: {e}", {})
                return []
        if self.f.phase != phase or power not in self.waiting_on():
            storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, out.text,
                             "arrived after the phase closed; ignored", out.usage())
            return []
        try:
            data = _json(out.text)
        except (ValueError, json.JSONDecodeError) as e:
            storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, out.text,
                             f"unreadable: {e}", out.usage())
            storage.log_action(self.game_id, power, phase, "response", out.text[:4000], False,
                               f"not a JSON object: {e}")
            return [f"Your reply was not a JSON object ({e}). Reply with only the JSON object."]
        storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, out.text, None, out.usage())
        return self._apply(power, phase, data)

    # -------------------------------------------------------------- inputs
    def _apply(self, power: str, phase: str, data: dict) -> list[str]:
        feedback: list[str] = []
        extra = set(data) - {"messages", "submit"}
        if extra:
            storage.log_action(self.game_id, power, phase, "response", data, False,
                               f"unknown fields ignored: {sorted(extra)}")
            feedback.append(f"Unknown fields were ignored: {sorted(extra)}. Use only messages and submit.")

        msgs = data.get("messages") or []
        if not isinstance(msgs, list):
            storage.log_action(self.game_id, power, phase, "message", msgs, False, "messages must be a list")
            feedback.append("messages must be a list of {\"to\", \"text\"} objects.")
            msgs = []
        for m in msgs:
            err = self._message_error(power, m)
            storage.log_action(self.game_id, power, phase, "message", m, err is None, err)
            if err:
                feedback.append(f"Message not sent: {err}.")
                continue
            storage.add_message(self.game_id, power, str(m["to"]).upper(), str(m["text"]).strip(), phase)

        sub = data.get("submit")
        if sub is not None:
            feedback += self._submit(power, phase, sub)
        return feedback

    @staticmethod
    def _message_error(power: str, m) -> str | None:
        if not isinstance(m, dict):
            return f"{m!r} is not a {{\"to\", \"text\"}} object"
        to, text = str(m.get("to", "")).upper(), m.get("text")
        if to != "GLOBAL" and to not in POWERS:
            return f"unknown recipient {m.get('to')!r}"
        if to == power:
            return "you cannot write to yourself"
        if not isinstance(text, str) or not text.strip():
            return "the message has no text"
        if len(text) > 2000:
            return f"the message is {len(text)} characters; the limit is 2000"
        return None

    def _submit(self, power: str, phase: str, sub) -> list[str]:
        if not isinstance(sub, dict):
            storage.log_action(self.game_id, power, phase, "submission", sub, False, "submit must be an object")
            return ["Submission refused: submit must be an object with orders, commitments and notes."]
        problems: list[str] = []
        legal = self.f.legal_orders(power)
        valid = {o for opts in legal.values() for o in opts}

        raw_orders = sub.get("orders", [])
        if not isinstance(raw_orders, list):
            problems.append("orders must be a list")
            storage.log_action(self.game_id, power, phase, "order", raw_orders, False, "orders must be a list")
            raw_orders = []
        orders, used = [], set()
        for o in raw_orders:
            norm = " ".join(str(o).upper().split())
            err = None
            if norm not in valid:
                err = f"{o!r} is not one of your legal orders"
            elif norm != "WAIVE":
                loc = norm.split()[1][:3]
                if loc in used:
                    err = f"{o!r} is a second order for {loc}"
                used.add(loc)
            storage.log_action(self.game_id, power, phase, "order", o, err is None, err)
            if err:
                problems.append(err)
            else:
                orders.append(norm)

        raw_sheet = sub.get("commitments", [])
        if not isinstance(raw_sheet, list):
            storage.log_action(self.game_id, power, phase, "commitment", raw_sheet, False,
                               "commitments must be a list")
            problems.append("commitments must be a list")
            raw_sheet = []
        chart = parse_chart(power, phase, {}, legal)
        for c in raw_sheet:
            if not isinstance(c, dict):
                err = f"{c!r} is not a commitment object"
            else:
                one = parse_chart(power, phase, {"commitments": [c]}, legal)
                err = one.rejected[0] if one.rejected else None
                if err is None:
                    chart.commitments += one.commitments
            storage.log_action(self.game_id, power, phase, "commitment", c, err is None, err)
            if err:
                problems.append(f"commitment sheet: {err}")

        if problems:
            storage.log_action(self.game_id, power, phase, "submission", sub, False,
                               f"refused: {len(problems)} problem(s)")
            return [f"Submission refused: {p}" for p in problems]

        self.f.submit(power, orders)
        storage.save_game(self.game_id, self.f.game)
        storage.save_chart(self.game_id, chart)
        notes = str(sub.get("notes") or "").strip()
        if notes:
            storage.add_note(self.game_id, power, phase, notes[:1500])
        storage.log_action(self.game_id, power, phase, "submission",
                           {"orders": orders, "commitments": [asdict(c) for c in chart.commitments]}, True)
        self.submitted(power)
        return []

    def _visible_press(self, power: str) -> list[dict]:
        """This phase's press and the most recent earlier phase that had any."""
        mine = storage.messages_for(self.game_id, power)
        earlier = [m["phase"] for m in mine if m["phase"] != self.f.phase]
        keep = {self.f.phase, *earlier[-1:]}
        return [m for m in mine if m["phase"] in keep]
