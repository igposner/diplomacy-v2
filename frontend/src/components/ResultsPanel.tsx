"use client";

import { useState } from "react";
import { BORDER_INK, FILL, LABEL_INK, PARCHMENT_DARK, type Power } from "@/lib/map";

export interface OrderResult {
  power: string; order: string; english: string; outcomes: string[]; ok: boolean;
}
export interface PhaseResult {
  phase: string;
  centerChanges: Record<string, string>;
  dislodged: Record<string, string[]>;
  orders: OrderResult[];
}

/* The engine's codes, in words. Anything unmapped shows as-is rather than hidden. */
const MEANING: Record<string, string> = {
  BOUNCE: "bounced", CUT: "support cut", DISLODGED: "dislodged", VOID: "void",
  NO_CONVOY: "no convoy", DISRUPTED: "convoy disrupted", DISBAND: "disbanded",
};

export default function ResultsPanel({ result, onMap, setOnMap }: {
  result: PhaseResult | null;
  onMap: boolean;
  setOnMap: (v: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  if (!result) return null;

  const failed = result.orders.filter((o) => !o.ok);
  const changes = Object.entries(result.centerChanges);
  const shown = open ? result.orders : failed;
  const title = result.phase.split(" ").slice(0, 2)
    .map((w) => w[0] + w.slice(1).toLowerCase()).join(" ");

  return (
    <section style={{ flex: "none" }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 8, paddingBottom: 6 }}>
        <h2 style={{ margin: 0, font: "italic 600 17px 'EB Garamond', Georgia, serif", color: LABEL_INK }}>
          {title}
        </h2>
        <span style={{ font: "500 9px 'IBM Plex Mono', monospace", letterSpacing: 1.2,
                       textTransform: "uppercase", color: "#7a6c50" }}>
          {failed.length === 0
            ? `all ${result.orders.length} orders succeeded`
            : `${failed.length} of ${result.orders.length} failed`}
        </span>
        <span style={{ flex: 1 }} />
        <button onClick={() => setOnMap(!onMap)}
                style={{ border: 0, background: "transparent", cursor: "pointer",
                         color: onMap ? "#8a6414" : "#7a6c50", marginRight: 8,
                         font: "italic 13px 'EB Garamond', serif", textDecoration: "underline" }}>
          {onMap ? "hide from map" : "show on map"}
        </button>
        <button onClick={() => setOpen((v) => !v)}
                style={{ border: 0, background: "transparent", color: "#7a6c50", cursor: "pointer",
                         font: "italic 13px 'EB Garamond', serif", textDecoration: "underline" }}>
          {open ? "failures only" : "show all"}
        </button>
      </header>

      <div style={{ maxHeight: 132, overflowY: "auto", display: "flex",
                    flexDirection: "column", gap: 3 }}>
        {shown.length === 0 && (
          <p style={{ margin: 0, font: "italic 14px 'EB Garamond', serif", color: "#7a6c50" }}>
            Nothing bounced or was cut.
          </p>
        )}
        {shown.map((o, i) => (
          <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
            <span style={{ width: 8, height: 8, flex: "none", borderRadius: 1,
                           background: FILL[o.power as Power] ?? "#7a6c50",
                           border: `1px solid ${BORDER_INK}`, alignSelf: "center" }} />
            <span style={{ font: "500 10.5px 'IBM Plex Mono', monospace", color: LABEL_INK,
                           flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis",
                           whiteSpace: "nowrap" }}>{o.order}</span>
            <span style={{ font: "italic 12.5px 'EB Garamond', serif",
                           color: o.ok ? "#42632c" : "#8f3328", whiteSpace: "nowrap" }}>
              {o.ok ? "held" : o.outcomes.map((c) => MEANING[c] ?? c.toLowerCase()).join(", ")}
            </span>
          </div>
        ))}
      </div>

      {changes.length > 0 && (
        <p style={{ margin: "7px 0 0", font: "italic 13px 'EB Garamond', serif", color: "#5f5540",
                    borderTop: `1px solid ${PARCHMENT_DARK}`, paddingTop: 6 }}>
          Centres changed hands: {changes.map(([c, p]) => `${c} to ${p.toLowerCase()}`).join(", ")}.
        </p>
      )}
    </section>
  );
}
