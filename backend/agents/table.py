"""The environment agents play in. One Table per game.

A movement phase runs like this:

    press rounds   every agent, in parallel, sees the same snapshot of the
                   board and its own press, and hands in a turn sheet
                   (messages, commitments, private plan; all optional).
                   Sheets are delivered only once every agent has answered,
                   so nobody in a round reads what another wrote in it.
    replies        a message arriving after an agent's last sheet earns that
                   agent one more sheet, up to a per-phase limit.
    orders         every agent, in parallel, gives orders and notes.

Retreat and adjustment phases skip straight to orders.

Failures are visible, never papered over: a call that errors or returns
nonsense is logged, gets one repair attempt, and after that the agent is
silent (press) or its units hold (orders). There is no bot fallback.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict

import storage
from agents.briefing import briefing, turn_prompt
from agents.models import Call, Completion, Model
from engine.facade import POWERS, Facade
from research.chart import describe_commitment, parse_chart


class CostCap(RuntimeError):
    pass


def _json(text: str) -> dict:
    t = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if fence:
        t = fence.group(1)
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


class Table:
    def __init__(self, game_id: str, facade: Facade, seats: dict[str, Model], *,
                 rounds: int = 2, human: str | None = None, disclose_human: bool = False,
                 characters: bool = False, max_replies: int = 3, cost_cap_usd: float = 5.0):
        self.game_id, self.f, self.seats = game_id, facade, seats
        self.rounds, self.human = rounds, human
        self.max_replies, self.cost_cap = max_replies, cost_cap_usd
        self.briefings = {p: briefing(p, rounds, human if disclose_human else None, characters) for p in seats}
        self.pending: set[str] = set()
        self.worker: asyncio.Task | None = None
        self.closing = False
        self.round = -1
        self._phase = None
        self._replies: dict[str, int] = {}
        self._sheets: dict[str, list[dict]] = {}

    # -------------------------------------------------------------- bookkeeping
    def _roll_phase(self) -> None:
        if self._phase != self.f.phase:
            self._phase = self.f.phase
            self._replies = {p: 0 for p in self.seats}
            self._sheets = {p: [] for p in self.seats}
            self.pending.clear()
            self.closing = False
            self.round = -1

    def active(self) -> list[str]:
        return [p for p in self.seats if self.f.legal_orders(p)]

    @property
    def negotiating(self) -> bool:
        return self.worker is not None and not self.worker.done()

    def _visible_press(self, power: str) -> list[dict]:
        """This phase's press and the most recent earlier phase that had any."""
        mine = storage.messages_for(self.game_id, power)
        earlier = [m["phase"] for m in mine if m["phase"] != self.f.phase]
        keep = {self.f.phase, *earlier[-1:]}
        return [m for m in mine if m["phase"] in keep]

    def _prompt(self, power: str, step: str, rnd: int) -> Call:
        state = self.f.state(power)
        legal = self.f.legal_orders(power)
        prompt = turn_prompt(
            power=power, state=state, legal=legal, step=step, round=rnd, rounds=self.rounds,
            press=self._visible_press(power), notes=storage.notes_for(self.game_id, power),
            last_result=storage.last_result(self.game_id), sheet_so_far=self._sheets.get(power, []))
        return Call(self.briefings[power], prompt, step, power, legal,
                    [p for p in POWERS if p != power])

    async def _ask(self, power: str, call: Call, label: str) -> dict | None:
        """One model call, logged in full, with one repair if the JSON is bad."""
        model = self.seats[power]
        for attempt in (0, 1):
            if storage.game_cost(self.game_id) >= self.cost_cap:
                storage.log_call(self.game_id, power, self.f.phase, label, model.name, call.prompt,
                                 None, f"cost cap ${self.cost_cap:.2f} reached", {})
                raise CostCap(f"game {self.game_id} reached its ${self.cost_cap:.2f} cap")
            try:
                out: Completion = await model.complete(call)
            except Exception as e:  # noqa: BLE001 -- recorded, not swallowed
                storage.log_call(self.game_id, power, self.f.phase, label, model.name, call.prompt,
                                 None, f"{type(e).__name__}: {e}", {})
                return None
            try:
                data = _json(out.text)
                storage.log_call(self.game_id, power, self.f.phase, label, model.name, call.prompt,
                                 out.text, None, out.usage())
                return data
            except (ValueError, json.JSONDecodeError) as e:
                storage.log_call(self.game_id, power, self.f.phase, label, model.name, call.prompt,
                                 out.text, f"bad JSON: {e}", out.usage())
                if attempt == 0:
                    call = Call(call.system, call.prompt + f"\n\nYour last reply was not a valid JSON "
                                f"object ({e}). Reply again with only the JSON object.",
                                "repair" if call.step == "orders" else call.step,
                                call.power, call.legal, call.others)
                    label = f"{label}:repair"
        return None

    # -------------------------------------------------------------- press
    async def _sheets_round(self, powers: list[str], step: str, rnd: int) -> None:
        calls = {p: self._prompt(p, step, rnd) for p in powers}     # one snapshot for all
        label = f"press:{rnd}" if step == "press" else "reply"
        answers = await asyncio.gather(*(self._ask(p, calls[p], label) for p in powers))
        for p, data in zip(powers, answers):
            self._deliver(p, data or {}, rnd if step == "press" else self.rounds + self._replies[p])

    def _deliver(self, power: str, data: dict, rnd: int) -> None:
        phase = self.f.phase
        chart = parse_chart(power, phase, data, self.f.legal_orders(power), round=rnd)
        for m in chart.messages:
            storage.add_message(self.game_id, power, m["to"], m["text"], phase)
            if m["to"] in self.seats:
                self._poke(m["to"], power)
            elif m["to"] == "GLOBAL":
                for p in self.seats:
                    self._poke(p, power)
        for c in chart.commitments:
            storage.add_message(self.game_id, power, c.recipient, describe_commitment(c), phase, "commitment")
            if c.recipient in self.seats:
                self._poke(c.recipient, power)
        storage.save_chart(self.game_id, chart)
        self._sheets[power].append({"round": rnd, "messages": chart.messages,
                                    "commitments": [asdict(c) for c in chart.commitments],
                                    "private_plan": chart.plan, "refused": chart.rejected})

    def _poke(self, power: str, sender: str) -> None:
        if power != sender and self.round >= self.rounds - 1:
            self.pending.add(power)      # during scheduled rounds, the next round will show it

    def message_from_human(self, recipient: str) -> None:
        """A human wrote. The agents it reaches answer without waiting for a round."""
        self._roll_phase()
        targets = list(self.seats) if recipient == "GLOBAL" else [recipient] if recipient in self.seats else []
        for p in targets:
            self.pending.add(p)
        if not self.negotiating and not self.closing and self.pending:
            self.worker = asyncio.create_task(self._replies_only())

    async def _replies_only(self) -> None:
        while self.pending and not self.closing:
            batch = [p for p in self.pending if self._replies[p] < self.max_replies and p in self.active()]
            self.pending.clear()
            if not batch:
                return
            for p in batch:
                self._replies[p] += 1
            await self._sheets_round(batch, "reply", -1)

    async def negotiate(self) -> None:
        """The scheduled rounds, then any replies they provoked."""
        self._roll_phase()
        if self.f.phase_type != "MOVEMENT" or self.f.done:
            return
        for rnd in range(self.rounds):
            if self.closing:
                return
            self.round = rnd
            powers = self.active()
            if powers:
                await self._sheets_round(powers, "press", rnd)
        await self._replies_only()

    def open_phase(self) -> None:
        """Start negotiating in the background (the human game)."""
        self._roll_phase()
        if self.f.phase_type == "MOVEMENT" and not self.f.done and not self.negotiating:
            self.worker = asyncio.create_task(self.negotiate())

    async def close_press(self) -> None:
        """No new rounds start; the one in flight is allowed to finish and be delivered."""
        self.closing = True
        if self.worker is not None:
            try:
                await self.worker
            except CostCap:
                pass

    # -------------------------------------------------------------- orders
    async def _orders_for(self, power: str) -> None:
        legal = self.f.legal_orders(power)
        if not legal:
            return
        valid = {o for opts in legal.values() for o in opts}
        call = self._prompt(power, "orders", 0)
        data = await self._ask(power, call, "orders") or {}
        chosen, bad = self._pick(data.get("orders"), valid, legal)
        if bad:
            fix = Call(call.system, call.prompt + "\n\nThese orders are not legal and were not accepted: "
                       + json.dumps(bad) + "\nChoose again, copying exactly from YOUR LEGAL ORDERS. "
                       "Repeat the orders that were fine too.", "repair", power, legal, call.others)
            again = await self._ask(power, fix, "orders:repair") or {}
            chosen2, bad2 = self._pick(again.get("orders"), valid, legal)
            if again.get("orders") is not None:
                chosen, bad = chosen2, bad2
                data["notes"] = again.get("notes", data.get("notes"))
            if bad:
                storage.log_call(self.game_id, power, self.f.phase, "orders:illegal", self.seats[power].name,
                                 "", json.dumps(bad), f"{len(bad)} illegal order(s) dropped; those units hold", {})
        if chosen:
            self.f.submit(power, chosen)
        notes = str(data.get("notes") or "").strip()
        if notes:
            storage.add_note(self.game_id, power, self.f.phase, notes[:1500])

    @staticmethod
    def _pick(raw, valid: set[str], legal: dict[str, list[str]]) -> tuple[list[str], list[str]]:
        if not isinstance(raw, list):
            return [], [] if raw is None else [str(raw)]
        chosen, bad, used = [], [], set()
        adjust = any(o.endswith((" B", " D")) or o == "WAIVE" for o in valid)
        for o in raw:
            o = " ".join(str(o).upper().split())
            if o not in valid:
                bad.append(o)
                continue
            loc = o.split()[1][:3] if o != "WAIVE" else None
            if loc and loc in used and not adjust:
                bad.append(f"{o} (a second order for the same unit)")
                continue
            if loc:
                used.add(loc)
            chosen.append(o)
        return chosen, bad

    async def orders(self) -> None:
        self._roll_phase()
        results = await asyncio.gather(*(self._orders_for(p) for p in self.seats if p != self.human),
                                       return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException) and not isinstance(r, CostCap):
                raise r      # over budget, units hold (already logged); anything else is a bug

    async def play_phase(self) -> None:
        """Headless: the whole phase, press then orders, nothing in the background."""
        self._roll_phase()
        try:
            await self.negotiate()
        except CostCap:
            pass
        await self.orders()
