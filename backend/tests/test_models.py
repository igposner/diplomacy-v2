"""The DeepSeek adapter, against a fake transport: no key, no network, no cost.

What it must get right is what a live run got wrong: these models think before
answering unless told not to, and thinking is billed and capped as output, so a
reply can come back empty with the whole budget spent.
"""
import asyncio, json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx

from agents.models import BadReply, Call, DeepSeek, deepseek_peak, make_model

n = 0
def ok(label):
    global n; n += 1; print("  ok", label)

SENT: list[dict] = []


def fake(reply: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        SENT.append(json.loads(request.content))
        return httpx.Response(200, json=reply)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def answer(content, tokens=120, hit=0, miss=900):
    return {"choices": [{"finish_reason": "stop" if content else "length",
                         "message": {"content": content, "reasoning_content": "" if content else "thinking..."}}],
            "usage": {"prompt_cache_hit_tokens": hit, "prompt_cache_miss_tokens": miss,
                      "completion_tokens": tokens}}


call = Call(system="briefing", prompt="your move", step="act", power="RUSSIA")


async def run() -> None:
    m = DeepSeek("deepseek-flash", key="test")
    m.client = fake(answer('{"messages": []}'))
    out = await m.complete(call)
    body = SENT[-1]
    assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"} and body["max_tokens"] == 4000
    assert out.text == '{"messages": []}'
    ok("by default it asks for JSON with thinking off, so the budget goes on the answer")

    t = DeepSeek("deepseek-flash", key="test", thinking=True)
    t.client = fake(answer('{"messages": []}', tokens=6500))
    await t.complete(call)
    assert SENT[-1]["thinking"] == {"type": "enabled"} and SENT[-1]["max_tokens"] == 8000
    assert t.name == "deepseek-flash:thinking", t.name
    ok("the thinking variant is a separate named model with room to reason")

    # what actually happened live: 4000 output tokens of reasoning, empty content
    m.client = fake(answer("", tokens=4000))
    try:
        await m.complete(call)
        raise AssertionError("an empty reply was accepted")
    except BadReply as e:
        assert "finish_reason=length" in str(e) and "4000" in str(e)
    ok("an empty reply is refused as a provider failure, with the token count that explains it")

    m.client = fake(answer("   "))
    try:
        await m.complete(call)
        raise AssertionError("whitespace was accepted as a reply")
    except BadReply:
        pass
    ok("whitespace counts as empty")

    m.client = fake(answer('{"a": 1}', tokens=1000, hit=800, miss=200))
    out = await m.complete(call)
    peak = deepseek_peak()
    p_hit, p_miss, p_out = (0.006, 0.30, 1.20) if peak else (0.003, 0.15, 0.60)
    assert out.input_tokens == 1000 and out.cached_tokens == 800 and out.output_tokens == 1000
    assert abs(out.cost_usd - (800 * p_hit + 200 * p_miss + 1000 * p_out) / 1e6) < 1e-12
    ok(f"cost counts cache hits apart from misses at the right rate ({'peak' if peak else 'off-peak'} now)")

    m.client = fake({"error": "nope"})
    async def bad(request):  # noqa: ANN001
        return httpx.Response(402, text="Insufficient Balance")
    m.client = httpx.AsyncClient(transport=httpx.MockTransport(bad))
    try:
        await m.complete(call)
        raise AssertionError("an HTTP error was swallowed")
    except RuntimeError as e:
        assert "402" in str(e) and "Insufficient Balance" in str(e)
    ok("an HTTP error is raised with its status and body, so a dead key or empty balance is obvious")

    os.environ["DEEPSEEK_API_KEY"] = "test"
    assert make_model("deepseek-flash").thinking is False
    assert make_model("deepseek-flash:thinking").thinking is True
    for bad_name in ("deepseek-flash:fast", "gpt-4"):
        try:
            make_model(bad_name)
            raise AssertionError(f"accepted {bad_name}")
        except ValueError:
            pass
    ok("model names are checked, including the thinking suffix")

    assert deepseek_peak(datetime(2026, 9, 16, 2, tzinfo=timezone.utc))
    assert not deepseek_peak(datetime(2026, 9, 16, 5, tzinfo=timezone.utc))
    assert not deepseek_peak(datetime(2026, 9, 13, 2, tzinfo=timezone.utc))  # a Sunday
    ok("peak hours are weekdays 01-04 and 06-10 UTC, which halves the bill outside them")


asyncio.run(run())
print(f"{n} model checks passed")
