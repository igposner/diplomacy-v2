"""The promise instrument, end to end through the real resolve path.

Charts go in, the human submits, the phase resolves, and each promise is judged
against the orders actually given, then survives a restart. Nothing a player
could use (verdicts, commitment sheets) is visible before the game is over.
"""
import asyncio, json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DIPLOMACY_DB"] = tempfile.mktemp(suffix=".sqlite3")

from fastapi import HTTPException

import main, storage
from engine.facade import VICTORY_CENTERS
from main import Message, NewGame, Orders
from research.chart import parse_chart


def chart(gid, f, power, data):
    c = parse_chart(power, f.phase, data, f.legal_orders(power))
    assert not c.rejected, c.rejected
    storage.save_chart(gid, c)


async def run() -> int:
    n = 0
    g = await main.new_game(NewGame(power="FRANCE", advance=0))
    gid = g["game_id"]
    f = main.LIVE[gid]
    phase = f.phase

    # Germany first offers France a support, then revises it in a later message to
    # "Munich holds". Its final sheet carries only the revised promise, plus one to
    # Russia to stay out of Silesia. Then it takes Burgundy and Silesia anyway.
    await main.send_message(gid, Message(sender="GERMANY", to="FRANCE", text="Munich supports you into Burgundy."))
    await main.send_message(gid, Message(sender="GERMANY", to="FRANCE", text="Change of plan: Munich just holds."))
    chart(gid, f, "GERMANY", {"commitments": [
        {"to": "FRANCE", "kind": "hold", "unit": "A MUN"},
        {"to": "RUSSIA", "kind": "no_enter", "province": "SIL"}]})
    f.submit("GERMANY", ["A MUN - BUR", "A BER - SIL", "F KIE H"])

    # Austria promises France (the human) to hold Vienna, and does.
    chart(gid, f, "AUSTRIA", {"commitments": [{"to": "FRANCE", "kind": "hold", "unit": "A VIE"}]})
    f.submit("AUSTRIA", ["A VIE H", "A BUD H", "F TRI H"])

    # England hands in an empty sheet. Italy talks but promises nothing.
    chart(gid, f, "ENGLAND", {"commitments": []})
    await main.send_message(gid, Message(sender="ITALY", to="FRANCE", text="Lovely weather in Piedmont."))
    await main.send_message(gid, Message(sender="FRANCE", to="GERMANY", text="Deal."))

    try:
        await main.research(gid)
        raise AssertionError("research data served mid-game")
    except HTTPException as e:
        assert e.status_code == 403
    n += 1; print("  ok research data is closed while the game is running")

    seen = json.dumps(await main.state(gid, "FRANCE")) + json.dumps(await main.read_messages(gid, "RUSSIA"))
    assert "no_enter" not in seen and "SIL" not in json.dumps(await main.read_messages(gid, "RUSSIA"))
    n += 1; print("  ok a commitment sheet appears nowhere a player can read")

    await main.submit(gid, Orders(power="FRANCE", orders=["A PAR - BUR"]))
    assert f.phase != phase
    v = {(x["commitment"]["speaker"], x["commitment"]["recipient"]): x for x in storage.verdicts_for(gid)}
    assert len(v) == 3, v
    assert v["GERMANY", "FRANCE"]["verdict"] == "BROKEN" and v["GERMANY", "FRANCE"]["commitment"]["kind"] == "hold"
    assert v["GERMANY", "RUSSIA"]["verdict"] == "BROKEN"
    assert v["AUSTRIA", "FRANCE"]["verdict"] == "KEPT"
    assert all("intent" not in x for x in v.values())
    n += 1; print("  ok resolving scores the final sheet against the final orders: the revised promise, not the first")

    # restart, then end the game with a French solo
    main.LIVE.clear(); main.HUMAN.clear()
    f = main.get(gid)
    scs = sorted(f.game.map.scs)
    f.game.set_centers("FRANCE", scs[:VICTORY_CENTERS])
    storage.save_game(gid, f.game)
    main.LIVE.clear()

    r = await main.research(gid)
    s = r["summary"]
    ger, aus, eng, ita = s["GERMANY"], s["AUSTRIA"], s["ENGLAND"], s["ITALY"]
    assert (ger["made"], ger["kept"], ger["broken"], ger["honesty"]) == (2, 0, 2, 0.0), ger
    assert "premeditatedShare" not in ger and "later" not in ger
    assert ger["toHumans"] == {"kept": 0, "broken": 1} and ger["toAgents"] == {"kept": 0, "broken": 1}
    n += 1; print("  ok Germany: two promises on its final sheet, both broken, split human vs agent")
    assert aus["honesty"] == 1.0 and aus["toHumans"]["kept"] == 1
    assert eng["honesty"] is None and eng["silence"] == 1.0, eng
    n += 1; print("  ok England's empty sheet is silence, and silence is not a perfect score")
    assert ita["honesty"] is None and ita["silence"] == 0.0, ita
    n += 1; print("  ok Italy talked without promising: not silent, still nothing to score")
    assert s["FRANCE"]["silence"] == 0.0 and s["RUSSIA"]["silence"] == 1.0
    n += 1; print("  ok every power with units is counted each phase, human included")
    return n


print(f"{asyncio.run(run())} research-record checks passed")
