"""The table agents play at, run like an online game with a clock.

Every phase (movement, retreats, builds and removals alike) is open for at most
`phase_seconds`, and never closes in its first `min_open` seconds. Once that
window has passed it closes as soon as every player with something to order has
submitted. Humans and agents are held to the same clock.

The window exists because a first run without it ended a phase in six seconds:
every agent wrote its messages and submitted in the same breath, so twenty
messages went out and not one reply was ever read. Submitting is not final --
orders may be revised, and messages answered, until the phase closes -- so the
sheet and orders that stand at the close are the ones that count.

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
import difflib
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


# JSON mode makes models echo the format back; it means nothing and is not a fault.
ECHOED = {"type"}


def _same(text: str) -> str:
    """Two messages are the same message if only spacing or case differs."""
    return " ".join(str(text).split()).lower()


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _at(stamp: str):
    from datetime import datetime
    return datetime.fromisoformat(stamp)


def _alike(a: str, b: str) -> float:
    """How much two messages say the same thing. Models paraphrase themselves."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _json(text: str) -> tuple[dict, str | None]:
    """The object, and a note if the reply needed rescuing. Models sometimes send
    two objects in a row; the first one is the answer."""
    t = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if fence:
        t = fence.group(1)
    data, end = json.JSONDecoder().raw_decode(t)
    if not isinstance(data, dict):
        raise ValueError("the reply was JSON but not an object")
    trailing = t[end:].strip()
    return data, (f"{len(trailing)} characters after the JSON object were ignored" if trailing else None)


class Table:
    def __init__(self, game_id: str, facade: Facade, seats: dict[str, Model], *,
                 resolve: Callable[[], Awaitable[None]], human: str | None = None,
                 phase_seconds: float = 120, min_open: float = 45.0, min_interval: float = 5.0,
                 idle_after: float = 45.0, final_call: float = 30.0, cost_cap_usd: float = 5.0,
                 characters: bool = False, idle_pause: float = 60.0,
                 unanswered_cap: int = 2, alike_enough: float = 0.8, follow_up_gap: float = 30.0):
        self.game_id, self.f, self.seats, self.human = game_id, facade, seats, human
        self.resolve = resolve
        self.phase_seconds, self.min_interval = phase_seconds, min_interval
        self.min_open = min(min_open, phase_seconds)
        self.idle_after, self.final_call, self.cost_cap = idle_after, final_call, cost_cap_usd
        self.briefings = {p: briefing(p, phase_seconds / 60, characters, self.min_open) for p in seats}
        self.opened = 0.0
        # A game plays on by itself, so it stops when nobody is watching it: the
        # browser asking for the state is what counts as watching.
        self.idle_pause = idle_pause
        # Nobody may keep talking at a player who has not answered: agents wrote
        # the same offer six ways in a row to a human who never replied.
        self.unanswered_cap, self.alike_enough = unanswered_cap, alike_enough
        self.follow_up_gap = follow_up_gap
        self.seen = time.monotonic()
        self.task: asyncio.Task | None = None
        self.phase_done = asyncio.Event()
        self.over_budget = False

    # -------------------------------------------------------------- the clock
    def must_submit(self) -> set[str]:
        return {p for p in POWERS if self.f.legal_orders(p)}

    def waiting_on(self) -> set[str]:
        return self.must_submit() - storage.submitted(self.game_id, self.f.phase)

    def watching(self) -> None:
        """The human asked for the state. Lifts an idle pause."""
        self.seen = time.monotonic()
        if self.human and storage.paused(self.game_id)[0] == "idle":
            self.resume()

    def unwatched(self) -> bool:
        return bool(self.human) and time.monotonic() - self.seen > self.idle_pause

    def pause(self, reason: str = "manual") -> None:
        if storage.paused(self.game_id)[0] is None:
            storage.pause(self.game_id, reason, self.seconds_left())

    def resume(self) -> None:
        left = storage.unpause(self.game_id)
        storage.set_deadline(self.game_id, time.time() + (left if left is not None else self.phase_seconds))

    @property
    def is_paused(self) -> bool:
        return storage.paused(self.game_id)[0] is not None

    def open_seconds(self) -> float:
        return time.monotonic() - self.opened

    def closing_now(self) -> bool:
        """Everyone is in and the negotiation window has passed."""
        return not self.waiting_on() and self.open_seconds() >= self.min_open

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
        self.opened = time.monotonic()
        self.phase_done = asyncio.Event()
        agents = [asyncio.create_task(self._agent(p, phase)) for p in self.seats if p != self.human]
        paused_at = None
        while True:
            if self.is_paused:
                paused_at = paused_at or time.monotonic()
                await asyncio.sleep(0.2)
                continue
            if paused_at is not None:      # the window does not run down while paused
                self.opened += time.monotonic() - paused_at
                paused_at = None
            if self.unwatched():
                self.pause("idle")
                continue
            if self.seconds_left() <= 0 or self.closing_now():
                break
            await asyncio.sleep(0.1)
        self.phase_done.set()
        for t in agents:
            t.cancel()
        await asyncio.gather(*agents, return_exceptions=True)
        for p in self.waiting_on() & set(self.seats):
            storage.log_action(self.game_id, p, phase, "deadline", {}, False,
                               "the deadline passed before a submission was accepted; units hold")
        storage.set_deadline(self.game_id, None)
        await self.resolve()

    def submitted(self, power: str) -> None:
        """Called for every accepted submission, human or agent. Not final: a
        later submission in the same phase replaces it."""
        storage.mark_submitted(self.game_id, self.f.phase, power)

    # -------------------------------------------------------------- one agent
    async def _agent(self, power: str, phase: str) -> None:
        if not self.f.legal_orders(power):
            return
        last_call = -1e9
        seen = 0
        feedback: list[str] = []
        warned = False
        first = True
        while not self.phase_done.is_set() and self.f.phase == phase:
            now = time.monotonic()
            left = self.seconds_left()
            inbox = [m for m in storage.messages_for(self.game_id, power)
                     if m["phase"] == phase and m["sender"] != power]
            newest = max((m["id"] for m in inbox), default=0)
            final = left <= self.final_call and not warned
            # A refused submission is worth another turn at once -- its orders are
            # not in. A refused message is not: it was told to stop, so waking it
            # straight back up would only have it try again.
            urgent = any(f.startswith(("Submission refused", "Your reply was not")) for f in feedback)
            due = first or newest > seen or urgent or final or now - last_call >= self.idle_after
            if self.is_paused:
                await asyncio.sleep(0.2)
                continue
            if not due or now - last_call < self.min_interval or self.over_budget:
                await asyncio.sleep(min(0.25, self.min_interval / 4))
                continue
            first, seen, last_call = False, newest, now
            warned = warned or final
            feedback = await self._act(power, phase, left, feedback, final)

    def prompt_for(self, power: str, phase: str, left: float = 0.0,
                   feedback: list[str] | None = None, final: bool = False) -> str:
        waiting = self.waiting_on()
        return turn_prompt(
            power=power, state=self.f.state(power), legal=self.f.legal_orders(power), seconds_left=left,
            submitted=self.must_submit() - waiting, waiting=waiting,
            press=self._visible_press(power), notes=storage.notes_for(self.game_id, power),
            last_result=storage.last_result(self.game_id), feedback=feedback or [], final_call=final,
            unanswered=self.unanswered(power, phase), owed=self.owed(power, phase),
            earlier=self._earlier())

    async def _act(self, power: str, phase: str, left: float, feedback: list[str], final: bool) -> list[str]:
        call = Call(self.briefings[power], self.prompt_for(power, phase, left, feedback, final),
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
        if self.f.phase != phase or self.phase_done.is_set():
            storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, out.text,
                             "arrived after the phase closed; ignored", out.usage())
            return []
        try:
            data, rescued = _json(out.text)
        except (ValueError, json.JSONDecodeError) as e:
            storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, out.text,
                             f"unreadable: {e}", out.usage())
            storage.log_action(self.game_id, power, phase, "response", out.text[:4000], False,
                               f"not a JSON object: {e}")
            return [f"Your reply was not a JSON object ({e}). Reply with only the JSON object."]
        storage.log_call(self.game_id, power, phase, "act", model.name, call.prompt, out.text, rescued, out.usage())
        if rescued:
            storage.log_action(self.game_id, power, phase, "response", out.text[:4000], False, rescued)
        return self._apply(power, phase, data)

    # -------------------------------------------------------------- inputs
    def _apply(self, power: str, phase: str, data: dict) -> list[str]:
        feedback: list[str] = []
        extra = set(data) - {"messages", "submit"} - ECHOED
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
            err = self._message_error(power, phase, m)
            storage.log_action(self.game_id, power, phase, "message", m, err is None, err)
            if err:
                feedback.append(f"Message not sent: {err}.")
                continue
            storage.add_message(self.game_id, power, str(m["to"]).upper(), str(m["text"]).strip(), phase)

        sub = data.get("submit")
        if sub is not None:
            feedback += self._submit(power, phase, sub)
        return feedback

    def _message_error(self, power: str, phase: str, m) -> str | None:
        if not isinstance(m, dict):
            return f"{m!r} is not a {{\"to\", \"text\"}} object"
        to, text = str(m.get("to", "")).upper(), m.get("text")
        if to == "GLOBAL":
            return "there is no public channel; write to a power by name"
        if to not in POWERS:
            return f"unknown recipient {m.get('to')!r}"
        if to == power:
            return "you cannot write to yourself"
        if not isinstance(text, str) or not text.strip():
            return "the message has no text"
        if len(text) > 2000:
            return f"the message is {len(text)} characters; the limit is 2000"
        thread = [x for x in storage.messages_for(self.game_id, power)
                  if x["phase"] == phase and to in (x["sender"], x["to"])]
        answered = max((x["id"] for x in thread if x["sender"] == to), default=0)
        mine = [x for x in thread if x["sender"] == power and x["to"] == to]
        said = _same(text)
        for earlier in mine:
            before = _same(earlier["text"])
            # Short notes ("agreed", "yes") are allowed to look alike; a reworded
            # speech is not. Only real messages are compared for paraphrase.
            same = said == before or (min(len(said), len(before)) > 40
                                      and _alike(said, before) >= self.alike_enough)
            if same:
                return (f"you have already said this to {to} this phase; say something new "
                        "or say nothing")
        waiting = [x for x in mine if x["id"] > answered]
        if len(waiting) >= self.unanswered_cap:
            return (f"{to} has not answered your last {len(waiting)} messages this phase; "
                    "wait for a reply before writing to them again")
        if waiting:
            since = (_now() - _at(waiting[-1]["at"])).total_seconds()
            if since < self.follow_up_gap:
                return (f"you wrote to {to} {int(since)} seconds ago and they have not answered; "
                        f"give them at least {int(self.follow_up_gap)} seconds to reply")
        return None

    def owed(self, power: str, phase: str) -> list[str]:
        """Who has written to this power and had no answer back. Agents read a
        message, submitted their orders, and said nothing; they need telling."""
        mine = [m for m in storage.messages_for(self.game_id, power) if m["phase"] == phase]
        out = []
        for other in POWERS:
            if other == power:
                continue
            theirs = [m for m in mine if m["sender"] == other]
            if not theirs:
                continue
            answered = max((m["id"] for m in mine if m["sender"] == power and m["to"] == other), default=0)
            waiting = [m for m in theirs if m["id"] > answered]
            if waiting:
                ago = int((_now() - _at(waiting[0]["at"])).total_seconds())
                out.append(f"{other} (wrote {ago}s ago, you have not replied)")
        return out

    def unanswered(self, power: str, phase: str) -> list[str]:
        """Who this power is waiting on, for its own turn prompt."""
        mine = [m for m in storage.messages_for(self.game_id, power) if m["phase"] == phase]
        out = []
        for other in POWERS:
            if other == power:
                continue
            answered = max((m["id"] for m in mine if m["sender"] == other), default=0)
            waiting = [m for m in mine if m["sender"] == power and m["to"] == other and m["id"] > answered]
            if waiting:
                out.append(f"{other} ({len(waiting)} message{'s' if len(waiting) > 1 else ''} unanswered)")
        return out

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

    def _earlier(self, phases: int = 3) -> list[dict]:
        """The phases before the last one, so a betrayal does not fall out of sight."""
        played = self.f.history()
        return played[-(phases + 1):-1] if len(played) > 1 else []

    def _visible_press(self, power: str) -> list[dict]:
        """This phase's press and the most recent earlier phase that had any."""
        mine = storage.messages_for(self.game_id, power)
        earlier = [m["phase"] for m in mine if m["phase"] != self.f.phase]
        keep = {self.f.phase, *earlier[-1:]}
        return [m for m in mine if m["phase"] in keep]
