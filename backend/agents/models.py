"""Model adapters. One interface; the table never knows which provider it talks to.

Every call returns text plus what it cost. Nothing here retries silently or
falls back to a bot: v1 hid a dead API behind a scripted fallback for weeks.
A failed call raises, and the table records the failure where it can be seen.
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

import httpx


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0

    def usage(self) -> dict:
        return {"input_tokens": self.input_tokens, "cached_tokens": self.cached_tokens,
                "output_tokens": self.output_tokens, "cost_usd": self.cost_usd,
                "latency_ms": self.latency_ms}


@dataclass
class Call:
    """What the table asks for. `legal`, `others` and `step` are for offline
    models only; a real model sees nothing but `system` and `prompt`."""
    system: str
    prompt: str
    step: str
    power: str
    legal: dict[str, list[str]] = field(default_factory=dict)
    others: list[str] = field(default_factory=list)


class Model(Protocol):
    name: str
    async def complete(self, call: Call) -> Completion: ...


# ---------------------------------------------------------------- DeepSeek
# USD per 1M tokens: (cache hit, cache miss, output), (off-peak, peak).
# api-docs.deepseek.com/quick_start/pricing, checked 2026-09-14.
DEEPSEEK_PRICES = {
    "deepseek-flash":  {"offpeak": (0.003, 0.15, 0.60), "peak": (0.006, 0.30, 1.20)},
    "deepseek-v4-pro": {"offpeak": (0.022, 0.66, 1.98), "peak": (0.044, 1.32, 3.96)},
}


def deepseek_peak(now: datetime | None = None) -> bool:
    """01:00-04:00 and 06:00-10:00 UTC, Monday to Friday."""
    now = now or datetime.now(timezone.utc)
    return now.weekday() < 5 and (1 <= now.hour < 4 or 6 <= now.hour < 10)


class MissingKey(RuntimeError):
    pass


class DeepSeek:
    url = "https://api.deepseek.com/chat/completions"

    def __init__(self, model: str = "deepseek-flash", key: str | None = None, timeout: float = 120):
        if model not in DEEPSEEK_PRICES:
            raise ValueError(f"unknown DeepSeek model {model!r}")
        self.name = model
        self.key = key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.key:
            raise MissingKey("DEEPSEEK_API_KEY is not set; put it in backend/.env")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def complete(self, call: Call) -> Completion:
        t0 = time.monotonic()
        r = await self.client.post(self.url, headers={"Authorization": f"Bearer {self.key}"}, json={
            "model": self.name,
            "messages": [{"role": "system", "content": call.system},
                         {"role": "user", "content": call.prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": 4000,
        })
        if r.status_code != 200:
            raise RuntimeError(f"DeepSeek HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        u = body.get("usage", {})
        hit = u.get("prompt_cache_hit_tokens", 0)
        miss = u.get("prompt_cache_miss_tokens", u.get("prompt_tokens", 0) - hit)
        out = u.get("completion_tokens", 0)
        p_hit, p_miss, p_out = DEEPSEEK_PRICES[self.name]["peak" if deepseek_peak() else "offpeak"]
        return Completion(
            text=body["choices"][0]["message"]["content"] or "",
            input_tokens=hit + miss, cached_tokens=hit, output_tokens=out,
            cost_usd=(hit * p_hit + miss * p_miss + out * p_out) / 1e6,
            latency_ms=int((time.monotonic() - t0) * 1000))


# ---------------------------------------------------------------- offline
class Scripted:
    """Answers from a function of the call. For tests: exact, free, no network."""
    def __init__(self, fn: Callable[[Call], str | dict], name: str = "scripted"):
        self.fn, self.name = fn, name

    async def complete(self, call: Call) -> Completion:
        out = self.fn(call)
        return Completion(out if isinstance(out, str) else json.dumps(out))


class Dummy:
    """A stand-in opponent for building the UI without a key: legal random orders,
    the occasional short note, often nothing at all. It is not an agent and never
    pretends to be one; games using it are marked with its name."""
    name = "dummy"

    def __init__(self, seed: int | None = None, submit_chance: float = 0.4):
        self.rng = random.Random(seed)
        self.submit_chance = submit_chance

    async def complete(self, call: Call) -> Completion:
        rng, out = self.rng, {}
        if call.others and rng.random() < 0.35:
            out["messages"] = [{"to": rng.choice(call.others), "text": rng.choice([
                "Noted. I have no designs on your border this season.",
                "What are you planning? I would rather know than guess.",
                "We should talk before autumn.",
                "Received. I will think on it."])}]
        if rng.random() < self.submit_chance or "Time is nearly up" in call.prompt:
            builds = any(o.endswith((" B", " D")) for opts in call.legal.values() for o in opts)
            orders = [] if builds else [rng.choice(opts) for opts in call.legal.values()]
            out["submit"] = {"orders": orders, "commitments": [], "notes": ""}
        return Completion(json.dumps(out))


def make_model(name: str) -> Model:
    if name in DEEPSEEK_PRICES:
        return DeepSeek(name)
    if name == "dummy":
        return Dummy()
    raise ValueError(f"unknown model {name!r}")
