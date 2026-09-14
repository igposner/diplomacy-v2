"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Board, { type BoardState } from "@/components/Board";
import OrdersPanel from "@/components/OrdersPanel";
import PressPanel, { type Press } from "@/components/PressPanel";
import type { PhaseResult } from "@/lib/results";
import { chips, click, hint, indexLegal, modes, targets, type Entry } from "@/lib/orderEntry";
import { BORDER_INK, FILL, LABEL_INK, PARCHMENT, PARCHMENT_DARK, TOKEN, type Power } from "@/lib/map";

const API = process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";
const ORDER: Power[] = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"];
const base = (p: string) => p.split("/")[0];
const unitOf = (order: string) => order.split(" ")[1];

interface State extends BoardState {
  humanPower: Power;
  phase: string; phaseType: string; done: boolean;
  orderable?: string[]; legalOrders?: Record<string, string[]>;
  lastResult?: PhaseResult | null;
}

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
  useEffect(() => { setDraft({}); setNote(null); setEntry({ kind: "idle" }); }, [state?.phase]);

  /* The seat belongs to the game, not the browser. */
  const me: Power | null = state?.humanPower ?? null;

  const ix = useMemo(
    () => (state?.legalOrders ? indexLegal(state.legalOrders) : null),
    [state?.legalOrders]
  );
  const highlights = useMemo(() => (ix ? targets(ix, entry) : new Set<string>()), [ix, entry]);

  const load = useCallback(async (id: string) => {
    const [s, m] = await Promise.all([
      fetch(`${API}/api/games/${id}/state`).then((r) => r.json()),
      fetch(`${API}/api/games/${id}/state`).then((r) => r.json())
        .then((s: State) => fetch(`${API}/api/games/${id}/messages?power=${s.humanPower}`)
          .then((r) => r.json())),
    ]);
    setState(s); setPress(m); setEntry({ kind: "idle" });
  }, []);

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
    if (!ix) return;
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
        setNote(`rejected: ${d?.detail?.orders?.join(", ") ?? r.status}`);
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
  const title = state
    ? state.phase.split(" ").slice(0, 2).map((w) => w[0] + w.slice(1).toLowerCase()).join(" ")
    : "Diplomacy";
  const drafted = Object.entries(draft).map(([loc, order]) => ({ loc, order }))
    .sort((a, b) => a.loc.localeCompare(b.loc));
  const unordered = (state?.orderable ?? []).filter((l) => !draft[l]).map(base);

  return (
    <main style={{
      height: "100vh", display: "flex", gap: 12, padding: 12, boxSizing: "border-box",
      background: `radial-gradient(circle at 25% 15%, ${PARCHMENT}, ${PARCHMENT_DARK})`,
      fontFamily: "'EB Garamond', Georgia, serif",
    }}>
      <div style={{
        flex: "1 1 auto", minWidth: 0, position: "relative", display: "flex", flexDirection: "column",
        border: `2px solid ${BORDER_INK}`, background: PARCHMENT, padding: "32px 10px 8px",
        boxShadow: "inset 0 0 36px rgba(90,70,35,.22), 0 2px 8px rgba(40,32,16,.28)",
      }}>
        <div style={{ position: "absolute", top: 6, left: 10, right: 10, display: "flex",
                      gap: 5, alignItems: "center", zIndex: 2 }}>
          {ORDER.map((p) => (
            <div key={p} style={{
              background: FILL[p], border: `1.5px solid ${BORDER_INK}`, borderRadius: 2,
              padding: "2px 7px", display: "flex", alignItems: "center", gap: 5,
              outline: p === seat ? `2px solid ${BORDER_INK}` : undefined,
            }}>
              <span style={{ font: "600 9px 'EB Garamond', serif", letterSpacing: 1.3,
                             color: "#fdfaf2", textTransform: "uppercase" }}>{p.slice(0, 3)}</span>
              <span style={{ font: "600 10px 'IBM Plex Mono', monospace", color: "#fdfaf2",
                             background: TOKEN[p], borderRadius: 2, padding: "0 4px" }}>{sc(p)}</span>
            </div>
          ))}
          <div style={{ flex: 1 }} />
          <button onClick={() => router.push("/")} disabled={busy}
                  style={{ font: "600 9px 'EB Garamond', serif", letterSpacing: 1.2,
                           textTransform: "uppercase", padding: "3px 8px", borderRadius: 2,
                           border: `1.5px solid ${BORDER_INK}`, background: "transparent",
                           color: LABEL_INK, cursor: busy ? "wait" : "pointer", marginRight: 10 }}>
            Lobby
          </button>
          <div style={{ font: "italic 600 17px 'EB Garamond', Georgia, serif", color: LABEL_INK,
                        whiteSpace: "nowrap" }}>
            {title}
            <span style={{ font: "500 8.5px 'IBM Plex Mono', monospace", letterSpacing: 1.2,
                           textTransform: "uppercase", color: "#7a6c50", marginLeft: 8 }}>
              {state?.phaseType.toLowerCase() ?? "loading"}
            </span>
          </div>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center",
                      justifyContent: "center" }}>
          <div style={{ aspectRatio: "1859 / 1404", maxWidth: "100%", maxHeight: "100%",
                        width: "100%", border: `1.5px solid ${BORDER_INK}`,
                        overflow: "hidden", background: "#b9d7e8" }}>
            {error && <p style={{ padding: 20, color: "#8f3328" }}>Backend unreachable: {error}</p>}
            {!error && !state && <p style={{ padding: 20, color: "#7a6c50" }}>Loading board…</p>}
            {state && (
              <Board state={state} me={seat} ix={ix} entry={entry} highlights={highlights}
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
            {ix ? hint(ix, entry) : "Loading…"}
          </span>
          {ix && modes(ix, entry).filter((m) => m.next || m.order).map((m) => (
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
          {ix && chips(ix, entry).map((o) => (
            <button key={o.order}
                    onClick={() => { record(o.order); setEntry({ kind: "idle" }); }}
                    style={{ font: "600 10px 'EB Garamond', serif", letterSpacing: 1.2,
                             textTransform: "uppercase", padding: "4px 9px", borderRadius: 2,
                             border: `1.5px solid ${BORDER_INK}`, background: "#8a6414",
                             color: "#fdfaf2", cursor: "pointer" }}>
              {o.label}
            </button>
          ))}
          {entry.kind !== "idle" && (
            <button onClick={() => setEntry({ kind: "idle" })}
                    style={{ border: 0, background: "transparent", color: "#7a6c50", cursor: "pointer",
                             font: "italic 13px 'EB Garamond', serif", textDecoration: "underline" }}>
              cancel
            </button>
          )}
        </div>
      </div>

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
                     phaseType={state?.phaseType ?? ""}
                     onSubmit={submit} busy={busy} note={note} />

        <div style={{ height: 1, background: PARCHMENT_DARK, flex: "none" }} />

        <PressPanel me={seat} messages={press} onSend={sendPress} />
      </aside>
    </main>
  );
}
