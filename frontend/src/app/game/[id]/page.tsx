"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Board, { type BoardState } from "@/components/Board";
import OrdersPanel from "@/components/OrdersPanel";
import PressPanel, { type Press } from "@/components/PressPanel";
import EndScreen, { type Outcome } from "@/components/EndScreen";
import type { PhaseResult } from "@/lib/results";
import { chips, click, hint, indexLegal, modes, targets, type Entry } from "@/lib/orderEntry";
import { BORDER_INK, FILL, LABEL_INK, PARCHMENT, PARCHMENT_DARK, TOKEN, type Power } from "@/lib/map";

const API = process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";
const ORDER: Power[] = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"];
const base = (p: string) => p.split("/")[0];
/* The draft is keyed by province ("SPA"), as the orderable list is, even when the
   order names a coast ("F SPA/SC - WES"). */
const unitOf = (order: string) => base(order.split(" ")[1]);

interface Clock { secondsLeft: number; submitted: string[]; waitingOn: string[]; youSubmitted: boolean }

interface State extends BoardState {
  humanPower: Power;
  phase: string; phaseType: string; done: boolean;
  orderable?: string[]; legalOrders?: Record<string, string[]>;
  lastResult?: PhaseResult | null;
  outcome?: Outcome | null;
  opponents?: "bots" | "agents";
  clock?: Clock;          // timed tables only
  myOrders?: string[];    // what the server holds for you, so a reload keeps your draft
}

/** A phase already played, as /history returns it. */
interface Past extends BoardState {
  phase: string;
  orders: { power: string; order: string; outcomes: string[]; ok: boolean }[];
}

/* "FALL 1903 RETREATS" -> ["Fall 1903", "retreats"]; the winter phase is called the build. */
const KIND: Record<string, string> = { MOVEMENT: "movement", RETREATS: "retreats", ADJUSTMENTS: "build" };
const phaseName = (long: string): [string, string] => {
  const [season, year, kind] = long.split(" ");
  return [`${season[0]}${season.slice(1).toLowerCase()} ${year}`, KIND[kind] ?? (kind ?? "").toLowerCase()];
};
const clockText = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const draftOf = (orders: string[]) =>
  Object.fromEntries(orders.map((o, i) => [o === "WAIVE" ? `WAIVE-${i}` : unitOf(o), o]));
const listNames = (ps: string[]) => {
  const n = ps.map((p) => p[0] + p.slice(1).toLowerCase());
  return n.length <= 1 ? n.join("") : `${n.slice(0, -1).join(", ")} and ${n[n.length - 1]}`;
};

export default function GamePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id ?? null;
  const [gameId, setGameId] = useState<string | null>(null);
  const [state, setState] = useState<State | null>(null);
  const [press, setPress] = useState<Press[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [entry, setEntry] = useState<Entry>({ kind: "idle" });
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [note, setNote] = useState<string | null>(null);
  // Failure marks are a report on the last turn, not part of the live board.
  const [review, setReview] = useState(false);
  const consumed = useRef(false);

  // A new phase means a new set of units to order; last turn's draft is void.
  // At a timed table the server may already hold orders for it (a reload).
  const [history, setHistory] = useState<Past[]>([]);
  const [view, setView] = useState<number | null>(null);   // null = the present
  const phaseRef = useRef<string | null>(null);
  useEffect(() => {
    setDraft(draftOf(state?.myOrders ?? [])); setNote(null); setEntry({ kind: "idle" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.phase]);

  /* The seat belongs to the game, not the browser. */
  const me: Power | null = state?.humanPower ?? null;

  const ix = useMemo(
    () => (state?.legalOrders ? indexLegal(state.legalOrders) : null),
    [state?.legalOrders]
  );
  const highlights = useMemo(() => (ix ? targets(ix, entry) : new Set<string>()), [ix, entry]);

  const [deadlineAt, setDeadlineAt] = useState<number | null>(null);
  const load = useCallback(async (id: string) => {
    const s: State = await fetch(`${API}/api/games/${id}/state`).then((r) => r.json());
    const [m, h] = await Promise.all([
      fetch(`${API}/api/games/${id}/messages?power=${s.humanPower}`).then((r) => r.json()),
      fetch(`${API}/api/games/${id}/history`).then((r) => r.json()),
    ]);
    phaseRef.current = s.phase;
    setState(s); setPress(m); setHistory(h); setEntry({ kind: "idle" });
    setDeadlineAt(s.clock ? Date.now() + s.clock.secondsLeft * 1000 : null);
  }, []);

  /* At a timed table the other players act while you think. Poll press and the
     clock without touching the board: a refresh must never drop a half-entered
     order. When the phase moves on, reload everything and show what happened. */
  const agentGame = state?.opponents === "agents";
  const humanPower = state?.humanPower;
  useEffect(() => {
    if (!gameId || !agentGame || !humanPower) return;
    let stop = false;
    const tick = async () => {
      try {
        const [m, s] = await Promise.all([
          fetch(`${API}/api/games/${gameId}/messages?power=${humanPower}`).then((r) => r.json()),
          fetch(`${API}/api/games/${gameId}/state`).then((r) => r.json()) as Promise<State>,
        ]);
        if (stop) return;
        setPress((old) => (old.length === m.length ? old : m));
        if (s.phase !== phaseRef.current) {
          await load(gameId);
          setReview(true);
          setView(null);
        } else {
          setState((old) => (old ? { ...old, clock: s.clock } : old));
          setDeadlineAt(s.clock ? Date.now() + s.clock.secondsLeft * 1000 : null);
        }
      } catch { /* the next tick will try again */ }
    };
    const t = setInterval(tick, 1500);
    return () => { stop = true; clearInterval(t); };
  }, [gameId, agentGame, humanPower, load]);

  // The countdown ticks locally between polls.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!agentGame) return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [agentGame]);
  const secondsLeft = deadlineAt ? Math.max(0, (deadlineAt - now) / 1000) : null;

  /* Orders you have entered but not submitted are saved as you go, so the clock
     running out plays them rather than holding everything. */
  const locked = !!state?.clock?.youSubmitted;
  useEffect(() => {
    if (!gameId || !agentGame || locked || !me) return;
    const t = setTimeout(() => {
      fetch(`${API}/api/games/${gameId}/orders`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ power: me, orders: Object.values(draft) }),
      }).catch(() => { /* the next change will try again */ });
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, gameId, agentGame, locked]);

  // Left and right arrows step through the turns, unless you are typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") return;
      if (e.key === "ArrowLeft") setView((v) => (history.length === 0 ? v : v === null ? history.length - 1 : Math.max(0, v - 1)));
      if (e.key === "ArrowRight") setView((v) => (v === null || v >= history.length - 1 ? null : v + 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [history.length]);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const r = await fetch(`${API}/api/games/${id}/state`);
        if (!r.ok) throw new Error(`no game ${id}`);
        try { localStorage.setItem("diplomacy.game", id); } catch { /* private window */ }
        setGameId(id);
        await load(id);
      } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    })();
  }, [id, load]);

  const record = (order: string) =>
    setDraft((d) => ({
      // WAIVE names no unit, so give each one its own slot.
      ...d,
      [order === "WAIVE" ? `WAIVE-${Object.keys(d).length}` : unitOf(order)]: order,
    }));

  /* Press on a unit selects it, so releasing over another province is a drag-move.
     A separate click on an already-selected unit is what orders a hold. */
  const onProvince = (p: string, phase: "down" | "up") => {
    if (!ix || view !== null || locked) return;
    if (review) setReview(false);   // you are playing now, not reviewing
    if (phase === "down") {
      consumed.current = false;
      // Pre-select on press so a drag becomes a move, but only where pressing
      // would select a unit. A buildable centre must reach its own prompt.
      if (entry.kind === "idle") {
        const peek = click(ix, entry, p);
        if (peek.next.kind === "unit" && !peek.order) {
          setEntry(peek.next);
          consumed.current = true;
        }
      }
      return;
    }
    if (consumed.current) { consumed.current = false; return; }
    const step = click(ix, entry, p);
    if (step.order) record(step.order);
    if (step.companion) record(step.companion);
    setEntry(step.next);
  };

  /* One action, as at a real table: hand in your orders and the turn resolves.
     Anything you left unordered holds. */
  const submit = async () => {
    if (!gameId || !me) return;
    setBusy(true);
    setNote(null);
    try {
      const r = await fetch(`${API}/api/games/${gameId}/submit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ power: me, orders: Object.values(draft) }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => null);
        setNote(`rejected: ${d?.detail?.orders?.join(", ") ?? d?.detail ?? r.status}`);
        return;
      }
      const d = await r.json();
      if (d.submitted) {           // a timed table: the phase resolves when everyone is in
        setState((old) => (old?.clock ? { ...old, clock: { ...old.clock, youSubmitted: true,
          waitingOn: d.waitingOn } } : old));
        setEntry({ kind: "idle" });
        return;
      }
      await load(gameId);
      setReview(true);   // the board shows what happened until you touch it
    } finally { setBusy(false); }
  };


  const sendPress = async (to: string, text: string) => {
    if (!gameId) return;
    await fetch(`${API}/api/games/${gameId}/messages`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender: me, to, text }),
    });
    await load(gameId);
  };

  const sc = (p: Power) => state?.powers[p]?.centers.length ?? 0;
  const seat: Power = me ?? "FRANCE";   // only used once state has arrived
  const past = view !== null ? history[view] ?? null : null;
  const [pastTitle, pastKind] = past ? phaseName(past.phase) : ["", ""];
  const [nowTitle, nowKind] = state ? phaseName(state.phase) : ["Diplomacy", "loading"];
  const waitingOthers = (state?.clock?.waitingOn ?? []).filter((p) => p !== me);
  const arrow = (dir: "back" | "forward") => {
    const disabled = dir === "back" ? history.length === 0 || view === 0 : view === null;
    return (
      <button aria-label={dir === "back" ? "Previous turn" : "Next turn"} disabled={disabled}
              onClick={() => setView((v) => dir === "back"
                ? (v === null ? history.length - 1 : Math.max(0, v - 1))
                : (v === null || v >= history.length - 1 ? null : v + 1))}
              style={{ width: 24, height: 22, display: "grid", placeItems: "center", padding: 0,
                       border: `1.5px solid ${BORDER_INK}`, borderRadius: 2, background: "transparent",
                       color: LABEL_INK, cursor: disabled ? "default" : "pointer",
                       opacity: disabled ? 0.3 : 1, font: "600 11px 'IBM Plex Mono', monospace" }}>
        {dir === "back" ? "◀" : "▶"}
      </button>
    );
  };
  const drafted = Object.entries(draft).map(([loc, order]) => ({ loc, order }))
    .sort((a, b) => a.loc.localeCompare(b.loc));
  const unordered = (state?.orderable ?? []).filter((l) => !draft[l]).map(base);

  /* A build turn is measured in builds, not in provinces you could build in:
     you are owed centres minus units, capped by the home centres actually free. */
  const adjust = state?.phaseType === "ADJUSTMENT" && me
    ? (() => {
        const p = state.powers[me];
        const delta = (p?.centers.length ?? 0) - (p?.units.length ?? 0);
        return {
          builds: Math.max(0, delta),
          removals: Math.max(0, -delta),
          placeable: Object.keys(state.legalOrders ?? {}).length,
        };
      })()
    : null;

  return (
    <main style={{
      height: "100vh", display: "flex", gap: 12, padding: 12, boxSizing: "border-box",
      background: `radial-gradient(circle at 25% 15%, ${PARCHMENT}, ${PARCHMENT_DARK})`,
      fontFamily: "'EB Garamond', Georgia, serif",
    }}>
      <div style={{
        flex: "1 1 auto", minWidth: 0, position: "relative", display: "flex", flexDirection: "column",
        border: `2px solid ${BORDER_INK}`, background: PARCHMENT, padding: "6px 10px 8px",
        boxShadow: "inset 0 0 36px rgba(90,70,35,.22), 0 2px 8px rgba(40,32,16,.28)",
      }}>
        {/* The strip above the board. It wraps rather than overflowing: on a narrow
            window the turn controls drop to a second row instead of into the sidebar. */}
        <div style={{ flex: "none", display: "flex", flexWrap: "wrap", alignItems: "center",
                      columnGap: 5, rowGap: 6, paddingBottom: 6 }}>
          <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
            {ORDER.map((p) => (
              <div key={p} title={past ? undefined : state?.clock?.submitted.includes(p) ? "orders submitted" : undefined}
                   style={{
                background: FILL[p], border: `1.5px solid ${BORDER_INK}`, borderRadius: 2,
                padding: "2px 7px", display: "flex", alignItems: "center", gap: 5,
                outline: p === seat ? `2px solid ${BORDER_INK}` : undefined,
              }}>
                <span style={{ font: "600 9px 'EB Garamond', serif", letterSpacing: 1.3,
                               color: "#fdfaf2", textTransform: "uppercase" }}>{p.slice(0, 3)}</span>
                <span style={{ font: "600 10px 'IBM Plex Mono', monospace", color: "#fdfaf2",
                               background: TOKEN[p], borderRadius: 2, padding: "0 4px" }}>
                  {past ? past.powers[p]?.centers.length ?? 0 : sc(p)}
                </span>
                {!past && state?.clock?.submitted.includes(p) && (
                  <span style={{ font: "700 10px 'IBM Plex Mono', monospace", color: "#fdfaf2" }}>✓</span>
                )}
              </div>
            ))}
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5 }}>
            <button onClick={() => router.push("/")} disabled={busy}
                    style={{ font: "600 9px 'EB Garamond', serif", letterSpacing: 1.2,
                             textTransform: "uppercase", padding: "3px 8px", borderRadius: 2,
                             border: `1.5px solid ${BORDER_INK}`, background: "transparent",
                             color: LABEL_INK, cursor: busy ? "wait" : "pointer", marginRight: 10 }}>
              Lobby
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {arrow("back")}
              {/* One line, the height of the arrows: a second line spills out of the strip. */}
              <div style={{ height: 22, minWidth: 200, display: "flex", alignItems: "baseline",
                            justifyContent: "center", gap: 7, padding: "0 4px", whiteSpace: "nowrap" }}>
                <span style={{ font: "italic 600 17px/22px 'EB Garamond', Georgia, serif", color: LABEL_INK }}>
                  {past ? pastTitle : "Present"}
                </span>
                <span style={{ font: "500 8.5px 'IBM Plex Mono', monospace", letterSpacing: 1.2,
                               textTransform: "uppercase", color: "#7a6c50" }}>
                  {past ? pastKind : `${nowTitle} · ${nowKind}`}
                </span>
              </div>
              {arrow("forward")}
              {secondsLeft !== null && !state?.done && (
                <span title="time left in this phase"
                      style={{ font: "600 13px 'IBM Plex Mono', monospace", minWidth: 40, textAlign: "right",
                               color: secondsLeft <= 20 ? "#8f3328" : LABEL_INK, marginLeft: 6 }}>
                  {clockText(secondsLeft)}
                </span>
              )}
            </div>
          </div>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center",
                      justifyContent: "center" }}>
          <div style={{ aspectRatio: "1859 / 1404", maxWidth: "100%", maxHeight: "100%",
                        width: "100%", border: `1.5px solid ${BORDER_INK}`,
                        overflow: "hidden", background: "#b9d7e8" }}>
            {error && <p style={{ padding: 20, color: "#8f3328" }}>Backend unreachable: {error}</p>}
            {!error && !state && <p style={{ padding: 20, color: "#7a6c50" }}>Loading board…</p>}
            {state && past && (
              <Board state={past} me={seat} ix={null} entry={{ kind: "idle" }} highlights={new Set()}
                     orders={past.orders} results={past.orders} onProvince={() => {}} />
            )}
            {state && !past && (
              <Board state={state} me={seat} ix={locked ? null : ix} entry={entry}
                     highlights={locked ? new Set() : highlights}
                     orders={Object.values(draft)}
                     results={review ? state.lastResult?.orders ?? null : null}
                     onProvince={onProvince} />
            )}
          </div>
        </div>

        {/* Running instruction, as webDiplomacy shows under the board. */}
        <div style={{ flex: "none", display: "flex", alignItems: "center", gap: 10, paddingTop: 6,
                      minHeight: 26 }}>
          <span style={{ font: "italic 15px 'EB Garamond', Georgia, serif", color: "#5f5540" }}>
            {past ? `${pastTitle}${pastKind === "movement" ? "" : ` ${pastKind}`}, as it was played. Failed orders are marked.`
              : locked ? (waitingOthers.length ? `Orders in. Waiting for ${listNames(waitingOthers)}.` : "Orders in. The turn is resolving…")
              : ix ? hint(ix, entry) : "Loading…"}
          </span>
          {past && (
            <button onClick={() => setView(null)}
                    style={{ font: "600 10px 'EB Garamond', serif", letterSpacing: 1.2,
                             textTransform: "uppercase", padding: "4px 9px", borderRadius: 2,
                             border: `1.5px solid ${BORDER_INK}`, background: "transparent",
                             color: LABEL_INK, cursor: "pointer" }}>
              Back to present
            </button>
          )}
          {ix && !past && !locked && modes(ix, entry).filter((m) => m.next || m.order).map((m) => (
            <button key={m.label} title={m.hint}
                    onClick={() => {
                      if (m.order) { record(m.order); setEntry({ kind: "idle" }); }
                      else if (m.next) setEntry(m.next);
                    }}
                    style={{ font: "600 10px 'EB Garamond', serif", letterSpacing: 1.2,
                             textTransform: "uppercase", padding: "4px 9px", borderRadius: 2,
                             border: `1.5px solid ${BORDER_INK}`, background: "transparent",
                             color: LABEL_INK, cursor: "pointer" }}>
              {m.label}
            </button>
          ))}
          {ix && !past && !locked && chips(ix, entry).map((o) => (
            <button key={o.order}
                    onClick={() => { record(o.order); setEntry({ kind: "idle" }); }}
                    style={{ font: "600 10px 'EB Garamond', serif", letterSpacing: 1.2,
                             textTransform: "uppercase", padding: "4px 9px", borderRadius: 2,
                             border: `1.5px solid ${BORDER_INK}`, background: "#8a6414",
                             color: "#fdfaf2", cursor: "pointer" }}>
              {o.label}
            </button>
          ))}
          {entry.kind !== "idle" && !past && (
            <button onClick={() => setEntry({ kind: "idle" })}
                    style={{ border: 0, background: "transparent", color: "#7a6c50", cursor: "pointer",
                             font: "italic 13px 'EB Garamond', serif", textDecoration: "underline" }}>
              cancel
            </button>
          )}
        </div>
      </div>

      {state?.outcome && me && <EndScreen outcome={state.outcome} me={me} />}

      <aside style={{
        width: 380, flex: "none", display: "flex", flexDirection: "column", gap: 10,
        border: `2px solid ${BORDER_INK}`, background: PARCHMENT, padding: 14, minHeight: 0,
        boxShadow: "inset 0 0 30px rgba(90,70,35,.2), 0 2px 8px rgba(40,32,16,.28)",
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8,
                      borderBottom: `1.5px solid ${PARCHMENT_DARK}`, paddingBottom: 8 }}>
          <span style={{ width: 11, height: 11, background: FILL[seat],
                         border: `1.5px solid ${BORDER_INK}` }} />
          <span style={{ font: "italic 600 20px 'EB Garamond', Georgia, serif", color: LABEL_INK }}>
            {seat[0] + seat.slice(1).toLowerCase()}
          </span>
          <span style={{ font: "500 9px 'IBM Plex Mono', monospace", letterSpacing: 1.2,
                         textTransform: "uppercase", color: "#7a6c50" }}>
            {sc(seat)} centres · {state?.powers[seat]?.units.length ?? 0} units
          </span>
        </div>

        <OrdersPanel power={seat} orders={drafted} unordered={unordered}
                     onClear={(loc) => setDraft((d) => { const n = { ...d }; delete n[loc]; return n; })}
                     onClearAll={() => setDraft({})}
                     phaseType={state?.phaseType ?? ""} adjust={adjust}
                     onSubmit={submit} busy={busy} note={note} locked={locked} />

        <div style={{ height: 1, background: PARCHMENT_DARK, flex: "none" }} />

        <PressPanel me={seat} messages={press} onSend={sendPress} agents={agentGame} />
      </aside>
    </main>
  );
}
