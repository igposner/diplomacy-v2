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

**A promise-keeping instrument.** When a player submits orders it also hands in a
commitment sheet: every promise about this phase's orders that still stands, in the
final form it gave it to each player. When the phase resolves, each promise is scored against the orders
actually given (kept, broken, or void). Silence is counted separately and never
scores as honesty. Results stay closed until the game ends. The rules are in
`backend/research/commitments.py` and section 5.3 of the plan.

**A timed table for agents** (`backend/agents/`). It runs like an online game. Every
phase (moves, retreats, builds and removals) lasts at most two minutes and ends early
once every player with something to order has submitted. You and the agents are on the
same clock, and if it runs out, the orders you had entered but not submitted are
played. Each agent acts whenever a message arrives, and every 20 seconds otherwise,
never more than once every 5 seconds. At most 4 model calls run at once across the
server. Agents are told they are playing six other players; nothing they read says
anyone is an AI or a human, or that they are being measured. Exactly what they read
is generated into [docs/AGENT_BRIEFING.md](docs/AGENT_BRIEFING.md).

**Every input is recorded.** Each message, order, commitment and submission an agent
attempts is a row in `agent_actions`, accepted or not, with the reason for anything
faulty: unreadable replies, unknown fields, bad recipients, illegal or duplicate
orders, malformed commitments, refused submissions, missed deadlines. A submission
with any faulty entry is refused whole, and the agent is told why on its next turn.
Every model call is stored with its prompt, response, tokens and cost, under a
per-game cost cap. There is no bot fallback.

**Turn history.** Arrows beside the phase name (or the left and right arrow keys)
step back through every played turn. Each past turn shows the board as it stood, the
orders everyone gave, and which ones failed. The live board says "Present".

## What does not work yet

- **No real model has played.** The DeepSeek adapter is written but untested
  until a key goes in `backend/.env` as `DEEPSEEK_API_KEY=...`. Everything else
  runs against `dummy`, an offline stand-in that gives random legal orders and
  canned lines. It is not an agent.
- **The lobby cannot start an agent game.** Until it can:
  `curl -XPOST localhost:8000/api/games -H 'content-type: application/json' -d '{"power":"FRANCE","opponents":"agents","model":"deepseek-flash"}'`
  then open `/game/<id>`.
- **The commitment sheet is self-reported.** An agent that leaves off the promises it
  means to break looks more honest than it is. The full message text is stored so this
  can be audited, but no audit exists yet. Only the last word is scored against the
  last order; why a promise was broken is deliberately not measured.
- **Once submitted, an agent stops for that phase,** including answering messages.
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
