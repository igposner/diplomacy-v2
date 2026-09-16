"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CompassRose from "@/components/CompassRose";
import SeaDragon from "@/components/SeaDragon";
import { BORDER_INK, LABEL_INK, PARCHMENT, PARCHMENT_DARK, TOKEN, type Power } from "@/lib/map";
import { CHARACTER, POWERS, homes } from "@/lib/powers";

const API = process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";

interface ModelOption { id: string; label: string; ready: boolean; note: string }
const INK = "#3b3428";

/* Rhumb lines: the radiating web on a portolan chart, struck from points on a
   hidden circle. Sixteen from each of three nodes, as the originals were drawn. */
function Rhumbs() {
  const nodes: [number, number][] = [[500, 330], [1180, 250], [820, 700]];
  const lines: React.ReactNode[] = [];
  nodes.forEach(([cx, cy], n) =>
    Array.from({ length: 16 }, (_, i) => {
      const a = (i * 22.5) * (Math.PI / 180);
      lines.push(
        <line key={`${n}-${i}`} x1={cx} y1={cy}
              x2={Number((cx + Math.cos(a) * 1700).toFixed(2))}
              y2={Number((cy + Math.sin(a) * 1700).toFixed(2))}
              stroke={i % 4 === 0 ? "#8a6414" : "#4a6b7c"}
              strokeWidth={i % 4 === 0 ? 0.8 : 0.5} strokeOpacity={0.17} />
      );
    })
  );
  return <>{lines}</>;
}

/* An empty ocean wants a monster. This one is Lorc's sea dragon from
   game-icons.net under CC BY 3.0 — a woodcut silhouette in the manner of the
   sea orms on the Carta Marina, rather than something drawn by hand here. */
function Monster() {
  return (
    <g transform="translate(44 596) rotate(-6) scale(0.52)" opacity={0.17}>
      <SeaDragon fill="#4a3d29" />
    </g>
  );
}

export default function Lobby() {
  const router = useRouter();
  const [pick, setPick] = useState<Power | null>(null);
  const [spinning, setSpinning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [resume, setResume] = useState<{ id: string; phase: string; power: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [table, setTable] = useState<"bots" | "agents">("bots");
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState("deepseek-flash");
  useEffect(() => {
    fetch(`${API}/api/models`).then((r) => r.json())
      .then((d) => setModels(d.models ?? []))
      .catch(() => setModels([]));   // the lobby still deals a scripted game
  }, []);
  const chosen = models.find((m) => m.id === model);
  const agentsReady = models.some((m) => m.ready);

  useEffect(() => {
    (async () => {
      try {
        let id: string | null = null;
        try { id = localStorage.getItem("diplomacy.game"); } catch { id = null; }
        const finished = async (gid: string) => {
          const r = await fetch(`${API}/api/games/${gid}/state`);
          if (!r.ok) return null;
          const s = await r.json();
          return s.done ? null : s;   // a finished game is not worth returning to
        };
        let s = id ? await finished(id) : null;
        if (!s) {
          const all = await fetch(`${API}/api/games`).then((r) => r.json());
          for (const g of Array.isArray(all) ? all : []) {
            s = await finished(g.id);
            if (s) { id = g.id; break; }
          }
        }
        if (!s || !id) return;
        setResume({ id, phase: s.phase, power: s.humanPower });
      } catch { /* the lobby still works without a game to resume */ }
    })();
  }, []);

  const random = useCallback(() => {
    setSpinning(true);
    const next = POWERS[Math.floor(Math.random() * POWERS.length)];
    setPick(next);
    setTimeout(() => setSpinning(false), 1200);
  }, []);

  const begin = async () => {
    if (!pick) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/games`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ power: pick, advance: 0, opponents: table, model }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => null);
        throw new Error(typeof d?.detail === "string" ? d.detail : `could not begin (${r.status})`);
      }
      const { game_id } = await r.json();
      try { localStorage.setItem("diplomacy.game", game_id); } catch { /* ignore */ }
      router.push(`/game/${game_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  const title = pick ? pick[0] + pick.slice(1).toLowerCase() : null;

  return (
    <main style={{ position: "relative", height: "100vh", overflow: "hidden",
                   background: PARCHMENT, fontFamily: "var(--font-serif), Georgia, serif" }}>
      {/* the sheet */}
      <svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" aria-hidden
           style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        <defs>
          <radialGradient id="age" cx="46%" cy="40%" r="78%">
            <stop offset="45%" stopColor="#efe4c6" />
            <stop offset="100%" stopColor="#c3ad7f" />
          </radialGradient>
          <filter id="fibre"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={4} />
            <feColorMatrix type="saturate" values="0" /></filter>
          <filter id="blot"><feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves={3} />
            <feDisplacementMap in="SourceGraphic" scale="70" /></filter>
        </defs>
        <rect width="1600" height="900" fill="url(#age)" />
        <Rhumbs />
        {/* damp stains, displaced so they are never circles */}
        <g filter="url(#blot)" fill="#8a6b3a" fillOpacity={0.09}>
          <circle cx="170" cy="760" r="120" /><circle cx="1470" cy="180" r="150" />
          <circle cx="1330" cy="820" r="95" />
        </g>
        <rect width="1600" height="900" filter="url(#fibre)" opacity={0.055}
              style={{ mixBlendMode: "multiply" }} />
        <Monster />
      </svg>

      <div style={{ position: "relative", height: "100%", display: "flex",
                    flexDirection: "column", padding: "clamp(18px,3vh,34px) clamp(20px,3vw,44px)",
                    boxSizing: "border-box", gap: 10 }}>
        {/* title block */}
        <header style={{ flex: "none" }}>
          <h1 style={{ margin: 0, font: "400 clamp(44px,6.2vw,86px)/0.95 var(--font-chart), Georgia, serif",
                       letterSpacing: "0.1em", color: INK, textShadow: "0 1px 0 rgba(255,250,235,.55)" }}>
            Diplomacy
          </h1>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 10, maxWidth: 620 }}>
            <span style={{ height: 1, flex: 1, background: INK, opacity: 0.35 }} />
            <span style={{ font: "400 13px var(--font-chart), Georgia, serif", letterSpacing: "0.34em",
                           color: INK, opacity: 0.72 }}>Europe · Anno 1901</span>
            <span style={{ height: 1, flex: 1, background: INK, opacity: 0.35 }} />
          </div>
          <p style={{ margin: "14px 0 0", maxWidth: 560, font: "17px/1.6 var(--font-serif), Georgia, serif",
                      color: "#4a4231" }}>
            Seven powers, thirty-four centres, and no dice. Take a seat at the table —
            choose a power from the rose, or strike the compass at its centre and let
            fortune decide for you.
          </p>
        </header>

        {/* rose and seat */}
        <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 36, minHeight: 0 }}>
          <div style={{ flex: "1 1 auto", minWidth: 0, height: "100%", minHeight: 0,
                        display: "grid", placeItems: "center" }}>
            <CompassRose selected={pick} onSelect={setPick} onRandom={random} spinning={spinning} />
          </div>

          <aside style={{ flex: "0 0 360px", maxHeight: "100%", overflowY: "auto" }}>
            {!pick && (
              <p style={{ font: "italic 19px/1.6 var(--font-serif), Georgia, serif", color: "#5b523e",
                          borderLeft: `2px solid ${PARCHMENT_DARK}`, paddingLeft: 16, margin: 0 }}>
                No power chosen yet.
              </p>
            )}
            {pick && (
              <div>
                <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                  <span style={{ width: 15, height: 15, background: TOKEN[pick],
                                 border: `1.5px solid ${BORDER_INK}` }} />
                  <h2 style={{ margin: 0, font: "400 38px/1 var(--font-chart), Georgia, serif",
                               letterSpacing: "0.05em", color: INK }}>{title}</h2>
                </div>
                <p style={{ margin: "14px 0 0", font: "17px/1.6 var(--font-serif), Georgia, serif",
                            color: "#4a4231" }}>{CHARACTER[pick]}</p>
                <dl style={{ margin: "20px 0 0", display: "grid", gridTemplateColumns: "auto 1fr",
                             gap: "7px 16px", font: "14px var(--font-serif), Georgia, serif" }}>
                  <dt style={{ font: "400 11px var(--font-chart), Georgia, serif",
                               letterSpacing: "0.2em", color: "#7a6c50", alignSelf: "center" }}>HOME</dt>
                  <dd style={{ margin: 0, font: "500 13px var(--font-mono), monospace",
                               letterSpacing: 1, color: LABEL_INK }}>{homes(pick).join("  ")}</dd>
                  <dt style={{ font: "400 11px var(--font-chart), Georgia, serif",
                               letterSpacing: "0.2em", color: "#7a6c50", alignSelf: "start",
                               paddingTop: 7 }}>TABLE</dt>
                  <dd style={{ margin: 0, color: "#4a4231" }}>
                    <div style={{ display: "flex", gap: 8 }}>
                      {(["bots", "agents"] as const).map((kind) => {
                        const on = table === kind;
                        const off = kind === "agents" && models.length > 0 && !agentsReady;
                        return (
                          <button key={kind} onClick={() => !off && setTable(kind)} disabled={off}
                                  style={{ font: "400 11px var(--font-chart), Georgia, serif",
                                           letterSpacing: "0.16em", textTransform: "uppercase",
                                           padding: "5px 11px", color: INK,
                                           border: `1.5px solid ${on ? BORDER_INK : PARCHMENT_DARK}`,
                                           background: on ? "rgba(255,250,235,.7)" : "transparent",
                                           cursor: off ? "not-allowed" : "pointer",
                                           opacity: off ? 0.45 : 1 }}>
                            {kind === "bots" ? "Scripted" : "Agents"}
                          </button>
                        );
                      })}
                    </div>
                    <p style={{ margin: "8px 0 0", font: "italic 14px/1.5 var(--font-serif), Georgia, serif",
                                color: "#6b6049" }}>
                      {table === "bots"
                        ? "Six scripted opponents. They play plausibly and never answer press."
                          + (models.length && !agentsReady ? ` Agents are unavailable: ${models[0].note}.` : "")
                        : agentsReady
                          ? "Six agents who read your press, answer it, and keep or break their word."
                          : (models[0]?.note ?? "Agents need a model key in backend/.env.")}
                    </p>
                    {table === "agents" && agentsReady && (
                      <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 8 }}>
                        {models.filter((m) => m.ready).map((m) => (
                          <button key={m.id} onClick={() => setModel(m.id)}
                                  style={{ font: "400 11px var(--font-chart), Georgia, serif",
                                           letterSpacing: "0.14em", padding: "4px 10px", color: INK,
                                           border: `1.5px solid ${model === m.id ? BORDER_INK : PARCHMENT_DARK}`,
                                           background: model === m.id ? "rgba(255,250,235,.7)" : "transparent",
                                           cursor: "pointer" }}>
                            {m.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </dd>
                </dl>
              </div>
            )}

            <button onClick={begin} disabled={!pick || busy}
                    style={{ marginTop: 26, display: "flex", alignItems: "center", gap: 14,
                             border: 0, background: "transparent", padding: 0,
                             cursor: pick && !busy ? "pointer" : "not-allowed",
                             opacity: pick ? 1 : 0.42 }}>
              <svg width="66" height="66" viewBox="-33 -33 66 66" aria-hidden>
                {/* a wax seal, pressed rather than printed */}
                <path d={Array.from({ length: 28 }, (_, i) => {
                  const a = (i / 28) * Math.PI * 2;
                  const r = 27 + (i % 3 === 0 ? 2.6 : i % 2 === 0 ? -2.2 : 0.8);
                  return `${i ? "L" : "M"} ${(Math.cos(a) * r).toFixed(1)} ${(Math.sin(a) * r).toFixed(1)}`;
                }).join(" ") + " Z"} fill="#8f2f28" stroke="#5e1d18" strokeWidth={1.4} />
                <circle r={20} fill="none" stroke="#d8a79e" strokeWidth={1.1} strokeOpacity={0.5} />
                <text y={7} textAnchor="middle" fontFamily="var(--font-chart), Georgia, serif"
                      fontSize={21} fill="#f3d9d4" fillOpacity={0.92}>
                  {pick ? pick[0] : "D"}
                </text>
              </svg>
              <span style={{ textAlign: "left" }}>
                <span style={{ display: "block", font: "400 21px var(--font-chart), Georgia, serif",
                               letterSpacing: "0.12em", color: INK }}>
                  {busy ? "Sealing…" : "Set the board"}
                </span>
                <span style={{ display: "block", font: "italic 14px var(--font-serif), Georgia, serif",
                               color: "#7a6c50", marginTop: 2 }}>
                  {!pick ? "choose a power first"
                    : table === "agents"
                      ? `Spring 1901 · you hold ${title} · ${chosen?.label ?? model}${chosen?.note ? `, ${chosen.note}` : ""}`
                      : `Spring 1901 · you hold ${title} · scripted table`}
                </span>
              </span>
            </button>

            {error && <p style={{ color: "#8f2f28", font: "italic 15px var(--font-serif), serif" }}>{error}</p>}
          </aside>
        </div>

        <footer style={{ flex: "none", display: "flex", alignItems: "center", gap: 18,
                         borderTop: `1px solid ${PARCHMENT_DARK}`, paddingTop: 14, marginTop: 10,
                         font: "15px var(--font-serif), Georgia, serif", color: "#6b6049" }}>
          {resume ? (
            <>
              <span>
                A game is already under way — {resume.power[0] + resume.power.slice(1).toLowerCase()},{" "}
                {resume.phase.split(" ").slice(0, 2).map((w) => w[0] + w.slice(1).toLowerCase()).join(" ")}.
              </span>
              <button onClick={() => router.push(`/game/${resume.id}`)}
                      style={{ border: `1.5px solid ${BORDER_INK}`, background: "transparent",
                               font: "400 12px var(--font-chart), Georgia, serif", letterSpacing: "0.16em",
                               color: INK, padding: "6px 14px", cursor: "pointer" }}>
                Return to it
              </button>
            </>
          ) : (
            <span>No game under way.</span>
          )}
          <span style={{ flex: 1 }} />
          <span style={{ font: "12px var(--font-serif), Georgia, serif", color: "#8a7f68" }}>
            Sea dragon by Lorc, game-icons.net, CC BY 3.0
          </span>
        </footer>
      </div>
    </main>
  );
}
