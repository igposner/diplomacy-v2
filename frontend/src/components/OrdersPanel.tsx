"use client";

import { BORDER_INK, LABEL_INK, PARCHMENT_DARK, TOKEN, type Power } from "@/lib/map";

const CARD = "#f3e9d0";
const UNIT = { A: "Army", F: "Fleet" } as const;

/** Plain English for the order list. Mirrors engine/orders.py describe(). */
export function describe(o: string): string {
  let m: RegExpMatchArray | null;
  if ((m = o.match(/^([AF]) (\S+) H$/))) return `${UNIT[m[1] as "A" | "F"]} ${m[2]} holds`;
  if ((m = o.match(/^([AF]) (\S+) - (\S+?)( VIA)?$/)))
    return `${UNIT[m[1] as "A" | "F"]} ${m[2]} to ${m[3]}${m[4] ? " by convoy" : ""}`;
  if ((m = o.match(/^([AF]) (\S+) S [AF] (\S+) - (\S+)$/)))
    return `${UNIT[m[1] as "A" | "F"]} ${m[2]} supports ${m[3]} into ${m[4]}`;
  if ((m = o.match(/^([AF]) (\S+) S [AF] (\S+)$/)))
    return `${UNIT[m[1] as "A" | "F"]} ${m[2]} supports ${m[3]}`;
  if ((m = o.match(/^F (\S+) C A (\S+) - (\S+)$/)))
    return `Fleet ${m[1]} convoys ${m[2]} to ${m[3]}`;
  if ((m = o.match(/^([AF]) (\S+) R (\S+)$/)))
    return `${UNIT[m[1] as "A" | "F"]} ${m[2]} retreats to ${m[3]}`;
  if ((m = o.match(/^([AF]) (\S+) D$/)))
    return `Disband the ${UNIT[m[1] as "A" | "F"].toLowerCase()} in ${m[2]}`;
  if ((m = o.match(/^([AF]) (\S+) B$/)))
    return `Build ${m[1] === "A" ? "an army" : "a fleet"} in ${m[2]}`;
  if (o === "WAIVE") return "Waive a build";
  return o;
}

export default function OrdersPanel({
  power, orders, unordered, phaseType, onClear, onClearAll, onSubmit, busy, note,
}: {
  power: Power;
  orders: { loc: string; order: string }[];
  unordered: string[];
  phaseType: string;
  onClear: (loc: string) => void;
  onClearAll: () => void;
  onSubmit: () => void;
  busy: boolean;
  note: string | null;
}) {
  const total = orders.length + unordered.length;
  return (
    <section style={{ display: "flex", flexDirection: "column", minHeight: 0, flex: "1 1 auto" }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "0 0 8px" }}>
        <h2 style={{ margin: 0, font: "italic 600 19px 'EB Garamond', Georgia, serif", color: LABEL_INK }}>
          Orders
        </h2>
        <span style={{ font: "500 9px 'IBM Plex Mono', monospace", letterSpacing: 1.2,
                       textTransform: "uppercase", color: "#7a6c50" }}>
          {total === 0 ? "nothing to order" : `${orders.length} of ${total} given`}
        </span>
        <span style={{ flex: 1 }} />
        {orders.length > 0 && (
          <button onClick={onClearAll}
                  style={{ border: 0, background: "transparent", color: "#7a6c50", cursor: "pointer",
                           font: "italic 13px 'EB Garamond', serif", textDecoration: "underline" }}>
            clear all
          </button>
        )}
      </header>

      <div style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto", display: "flex",
                    flexDirection: "column", gap: 4 }}>
        {total === 0 && (
          <p style={{ font: "italic 15px 'EB Garamond', serif", color: "#7a6c50", margin: 0 }}>
            No units of yours need orders this phase.
          </p>
        )}
        {orders.map(({ loc, order }) => (
          <div key={loc} style={{ display: "flex", alignItems: "center", gap: 8,
                                  background: CARD, border: `1px solid ${PARCHMENT_DARK}`,
                                  borderRadius: 2, padding: "5px 7px" }}>
            <span style={{ font: "600 10px 'IBM Plex Mono', monospace", color: "#fdfaf2",
                           background: TOKEN[power], borderRadius: 2, padding: "2px 5px",
                           minWidth: 42, textAlign: "center" }}>{loc}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ font: "15px 'EB Garamond', Georgia, serif", color: LABEL_INK,
                            lineHeight: 1.2 }}>{describe(order)}</div>
              <div style={{ font: "500 10px 'IBM Plex Mono', monospace", color: "#8d7f62",
                            marginTop: 1 }}>{order}</div>
            </div>
            <button onClick={() => onClear(loc)} aria-label={`Clear ${loc}`}
                    style={{ border: 0, background: "transparent", cursor: "pointer",
                             color: "#8d7f62", font: "600 13px 'IBM Plex Mono', monospace" }}>×</button>
          </div>
        ))}
        {unordered.length > 0 && (
          <p style={{ font: "italic 13px 'EB Garamond', serif", color: "#8f6a2a", margin: "6px 0 0" }}>
            {unordered.join(", ")} {unordered.length === 1 ? "has" : "have"} no order yet
            and will {phaseType === "ADJUSTMENT" ? "be waived" : "hold"}.
          </p>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, paddingTop: 10, flexWrap: "wrap" }}>
        {/* One action. Orders go in, the turn resolves, everything moves at once. */}
        <button onClick={onSubmit} disabled={busy}
                style={{ font: "600 11px 'EB Garamond', serif", letterSpacing: 1.3,
                         textTransform: "uppercase", padding: "9px 15px", borderRadius: 2,
                         border: `1.5px solid ${BORDER_INK}`, background: "#8a6414",
                         color: "#fdfaf2", cursor: busy ? "wait" : "pointer" }}>
          {busy ? "Orders going in…" : "Submit orders"}
        </button>
        {note && (
          <span style={{ font: "italic 13px 'EB Garamond', serif",
                         color: note.startsWith("rejected") ? "#8f3328" : "#42632c" }}>{note}</span>
        )}
      </div>
    </section>
  );
}
