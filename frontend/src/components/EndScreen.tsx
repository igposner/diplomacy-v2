"use client";

import { useRouter } from "next/navigation";
import Flag from "@/components/Flags";
import { BORDER_INK, FILL, TOKEN, PARCHMENT, PARCHMENT_DARK, type Power } from "@/lib/map";

const INK = "#3b3428";

export interface Outcome {
  kind: "solo" | "draw";
  winner: Power | null;
  centers?: number;
  year: number;
  standings: { power: string; centers: number; units: number }[];
  leaders?: string[];
}

const title = (p: string) => p[0] + p.slice(1).toLowerCase();

export default function EndScreen({ outcome, me }: { outcome: Outcome; me: Power }) {
  const router = useRouter();
  const won = outcome.kind === "solo" && outcome.winner === me;
  const victor = outcome.winner;
  /* The sheet takes the winner's colours; a draw keeps the parchment. */
  const accent = victor ? TOKEN[victor] : INK;
  const wash = victor ? FILL[victor] : PARCHMENT_DARK;
  const mine = outcome.standings.find((r) => r.power === me);

  const heading = outcome.kind === "draw" ? "Stalemate"
                : won ? "Victory" : "Defeat";
  const line = outcome.kind === "draw"
    ? `No power reached eighteen centres by ${outcome.year}. The board is scored where it stands.`
    : won
      ? `You hold ${outcome.centers} of the thirty-four centres. Europe is yours.`
      : `${title(victor!)} holds ${outcome.centers} of the thirty-four centres. You finish with ${mine?.centers ?? 0}.`;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 50, display: "grid", placeItems: "center",
      padding: 24, boxSizing: "border-box",
      background: `radial-gradient(circle at 50% 38%, ${wash} 0%, ${PARCHMENT} 45%, ${PARCHMENT_DARK} 100%)`,
      fontFamily: "var(--font-serif), Georgia, serif",
    }}>
      <div style={{
        width: "min(720px, 100%)", maxHeight: "100%", overflowY: "auto", textAlign: "center",
        border: `2px solid ${BORDER_INK}`, background: PARCHMENT, padding: "clamp(24px,5vh,52px) clamp(24px,5vw,56px)",
        boxShadow: `inset 0 0 50px rgba(90,70,35,.28), 0 6px 30px rgba(40,32,16,.4)`,
      }}>
        {victor && (
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 22 }}>
            <div style={{ border: `2px solid ${BORDER_INK}`, boxShadow: "0 3px 12px rgba(40,32,16,.4)" }}>
              <Flag power={victor} height={96} />
            </div>
          </div>
        )}

        <h1 style={{ margin: 0, font: "400 clamp(46px,8vw,78px)/0.95 var(--font-chart), Georgia, serif",
                     letterSpacing: "0.09em", color: accent,
                     textShadow: "0 1px 0 rgba(255,250,235,.6)" }}>
          {heading}
        </h1>

        <div style={{ display: "flex", alignItems: "center", gap: 14, margin: "16px auto 0",
                      maxWidth: 440 }}>
          <span style={{ height: 1, flex: 1, background: INK, opacity: 0.35 }} />
          <span style={{ font: "400 12px var(--font-chart), Georgia, serif", letterSpacing: "0.3em",
                         color: INK, opacity: 0.72 }}>
            {victor ? `${title(victor)} · ${outcome.year}` : `Europe · ${outcome.year}`}
          </span>
          <span style={{ height: 1, flex: 1, background: INK, opacity: 0.35 }} />
        </div>

        <p style={{ margin: "18px auto 0", maxWidth: "48ch",
                    font: "18px/1.6 var(--font-serif), Georgia, serif", color: "#4a4231" }}>
          {line}
        </p>

        <table style={{ margin: "26px auto 0", borderCollapse: "collapse", minWidth: 320,
                        fontVariantNumeric: "tabular-nums" }}>
          <tbody>
            {outcome.standings.map((r) => {
              const you = r.power === me;
              return (
                <tr key={r.power} style={{ borderTop: `1px solid ${PARCHMENT_DARK}` }}>
                  <td style={{ padding: "6px 10px", textAlign: "left" }}>
                    <span style={{ display: "inline-block", width: 11, height: 11, marginRight: 9,
                                   background: FILL[r.power as Power],
                                   border: `1.5px solid ${BORDER_INK}`, verticalAlign: "-1px" }} />
                    <span style={{ font: `400 15px var(--font-chart), Georgia, serif`,
                                   letterSpacing: "0.06em",
                                   color: INK, opacity: r.centers ? 1 : 0.45 }}>
                      {title(r.power)}
                    </span>
                    {you && <span style={{ font: "italic 13px var(--font-serif), serif",
                                           color: "#7a6c50", marginLeft: 8 }}>you</span>}
                  </td>
                  <td style={{ padding: "6px 10px", textAlign: "right",
                               font: "500 14px var(--font-mono), monospace", color: INK,
                               opacity: r.centers ? 1 : 0.45 }}>
                    {r.centers === 0 ? "out" : `${r.centers} ${r.centers === 1 ? "centre" : "centres"}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <button onClick={() => router.push("/")}
                style={{ marginTop: 30, border: `1.5px solid ${BORDER_INK}`, background: accent,
                         color: "#fdfaf2", font: "400 16px var(--font-chart), Georgia, serif",
                         letterSpacing: "0.14em", padding: "11px 26px", cursor: "pointer" }}>
          Take another seat
        </button>
      </div>
    </div>
  );
}
