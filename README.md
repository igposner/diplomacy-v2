# Diplomacy

A playable game of Diplomacy against bots, built to become a benchmark for how
well language models negotiate. Two shapes, one codebase: a game you can sit
down to, and a harness that records everything so agents can be scored on it.

The full plan, including budget and licensing, is in [docs/PLAN.md](docs/PLAN.md).

---

## Running it

Two terminals. Backend first:

```bash
cd backend && ./venv/bin/uvicorn main:app --port 8000
```

Then the frontend:

```bash
cd frontend && npm run dev
```

Open <http://localhost:3000>. Pick a power from the compass, or strike its centre
to let fortune decide.

To check nothing is broken without opening a browser:

```bash
./backend/check.sh          # rules gate, map build, a full scripted game, persistence, victory
cd frontend && npm run test:orders && npx tsc --noEmit
```

---

## What works today

**Rules.** The [`diplomacy`](https://github.com/diplomacy/diplomacy) package
adjudicates. `engine/facade.py` is the only module that touches it, so a change
in the engine's surface is a change in one file. Its own 160-case DATC suite
runs on every check.

**The board.** Generated from the package's `standard.svg` at build time, not
loaded at runtime. Orders are given by clicking, following Backstabbr: click a
unit then its destination to move, click it twice to hold, then Support, Convoy,
Retreat or Disband from the buttons that appear. Everything offered comes from
the engine's own list of legal orders, so an illegal order cannot be built.

**A turn.** Put in orders for the units you care about and press Submit.
Everything resolves at once and anything you left alone holds. Retreats and
builds arrive as their own turns. Build turns count what you are owed, which is
centres minus units.

**Persistence.** SQLite behind the facade. A game survives a restart with its
pending orders and press intact, and the browser returns to the game you were in.

**Press.** Messages to any power or to everyone, with visibility enforced in the
query rather than the browser.

**An ending.** A solo at eighteen centres ends the game, with a victory or defeat
screen in the winning power's colours and their 1901 flag.

**A promise-keeping instrument.** Each turn an agent may hand in a commitment
chart: messages, structured promises to named powers, and a private plan. Any of it
may be empty, since nobody has to say anything. When the phase resolves, every
promise is scored against the orders actually given (kept, broken, or void), and a
broken one is marked premeditated if the private plan already broke it. Silence is
counted separately and never scores as honesty. Results are closed until the game
ends. The rules are in `backend/research/commitments.py` and section 5.3 of the plan.
Agents now hand these in; no real model has played yet.

**An environment for agents** (`backend/agents/`). Each agent gets a briefing when
the game starts: the rules, order syntax, how a turn works, and its turn sheet. It
is told plainly that it never has to say anything. Each movement phase runs two
press rounds. Every agent answers from the same snapshot, so nobody reads what
someone else wrote in the same round. A message arriving after the last round earns
its recipient a reply turn, capped per phase. Then every agent gives orders and
writes notes for its next turn. Agents see only their own press and the board;
private plans reach nobody. An illegal order or unparseable reply gets one repair
call; after that the unit holds. A provider failure is logged, and there is no bot
fallback. Every call is stored with its prompt, response, tokens and cost, and
each game has a cost cap. In the browser, agent messages appear as they arrive,
and commitments are set apart from ordinary chat.

By default agents are not told their promises are scored, not told which seat is
human, and not given a character. Some of the old character sketches carry
attitudes to betrayal, which would make honesty a property of the seat.

## What does not work yet

- **No real model has played.** The DeepSeek adapter is written but untested
  until a key goes in `backend/.env` as `DEEPSEEK_API_KEY=...`. Everything else
  runs against `dummy`, an offline stand-in that gives random legal orders and
  canned lines. It is not an agent.
- **The lobby cannot start an agent game.** Until it can:
  `curl -XPOST localhost:8000/api/games -H 'content-type: application/json' -d '{"power":"FRANCE","opponents":"agents","model":"deepseek-flash"}'`
  then open `/game/<id>`.
- **No deadlines.** If you submit before the agents' press rounds finish, the round
  in flight completes and the rest are skipped.
- **No history.** You can see the phase that just resolved, not earlier ones.
- **No benchmark harness yet.** `scripts/play_agents.py` plays a headless game and
  prints cost, failures and promise-keeping; there is no multi-game runner or
  leaderboard.
- **One human seat.** The other six are always scripted.

---

## What comes next

1. **A first real game.** One headless phase on `deepseek-flash`, with every prompt
   and response read by hand, then a full game. Checks: do agents use the turn
   sheet, how often do they promise only in prose, how many illegal orders.
2. **Lobby choice of opponents,** and a second cheap model for the pilot.
3. **The harness.** Headless games, an invalid-order rate, promise-keeping and
   silence rates per model from the commitment charts, and a leaderboard. The
   first run is a ~$30 self-play pilot on `deepseek-flash`.

Cost is the reason the order matters: a full seven-agent game is roughly 4M input
and 340K output tokens. On `deepseek-flash` that is about $1.40 at peak rates and
half that off-peak, which is what makes iteration affordable. See the budget
section of the plan.

---

## Layout

```
backend/
  engine/facade.py     the only module that touches diplomacy.Game
  engine/orders.py     the only module that knows order syntax
  scripts/build_map.py standard.svg -> map data, with seven traps asserted
  storage.py           SQLite: saved games, press, charts, agent calls, notes
  agents/              briefing, turn prompt, the table, model adapters
  research/            commitment charts and the promise-keeping rules
  scripts/play_agents.py  a headless game of seven agents
  main.py              FastAPI
  bots/                scripted opponents
frontend/src/
  lib/orderEntry.ts    the click model, derived from legal orders
  lib/map.ts           map data, palette, anchors
  components/Board.tsx the board
  app/page.tsx         lobby
  app/game/[id]        the game
design/                the design canvas and the scripts that generate it
```

## The map file has seven traps

Every one fails silently, and `scripts/build_map.py` asserts against all of them.
Worth knowing before touching the map:

1. Province paths sit inside `<g transform="translate(-195 -170)">` while the
   unit, label and centre anchors sit outside it. Miss this and every province
   renders 195px from its own units.
2. The gaps between province polygons **are** the borders: the layer opens with a
   black rect and the polygons sit on top with 0–7 units between them. Put the
   sea colour behind them and every border becomes a river.
3. Four shapes carry no province id (Iceland and Ireland, and three straits) and
   are interleaved among the seas. Filtering by id leaves black holes.
4. Five sea provinces use ids the engine does not know: `MID`/`MAO`, `GOL`/`LYO`,
   `TYN`/`TYS`, `NAT`/`NAO`, `NRG`/`NWG`.
5. Centre markers live in a different layer, offset by half a 20px box.
6. Three label anchors parse to junk from legend text.
7. Five sea labels are multi-word and miss a three-letter scan.

---

## Licensing

The `diplomacy` engine is **AGPL-3.0**, so this project is bound by copyleft.
Decide deliberately before making it public or running it as a service.

Borrowed, with thanks:

- Province colours derive from [Radix Colors](https://github.com/radix-ui/colors) (MIT).
- The sea dragon on the lobby is by Lorc, [game-icons.net](https://game-icons.net/1x1/lorc/sea-dragon.html) (CC BY 3.0).
- The Union Flag and Ottoman flag constructions are public-domain SVGs from
  Wikimedia Commons; the other five flags are drawn here.
