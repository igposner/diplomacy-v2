"use client";

import { BEARING, POWERS } from "@/lib/powers";
import { BORDER_INK, FILL, TOKEN, type Power } from "@/lib/map";

/* Server and client must render byte-identical coordinates or React reports a
   hydration mismatch, so every computed number goes through this. */
const n = (v: number) => Number(v.toFixed(2));

const R = 172;          // rose radius
const RING = 236;       // where the powers sit
const INK = "#3b3428";
const PAPER_HI = "#f0e5c8";

/** A 32-point rose: cardinals long, then ordinals, half-winds, quarter-winds.
    Each point is two triangles so the light side catches and the dark side reads. */
function points() {
  const out: React.ReactNode[] = [];
    for (let i = 0; i < 32; i++) {
    const rank = i % 8 === 0 ? 0 : i % 4 === 0 ? 2 : i % 2 === 0 ? 1 : 3;
    const len = [R, R * 0.58, R * 0.8, R * 0.42][rank];
    const w = [13, 6, 9, 4][rank];
    const a = (i * 11.25 - 90) * (Math.PI / 180);
    const tip = [n(Math.cos(a) * len), n(Math.sin(a) * len)];
    const l = [n(Math.cos(a - Math.PI / 2) * w), n(Math.sin(a - Math.PI / 2) * w)];
    const r = [n(Math.cos(a + Math.PI / 2) * w), n(Math.sin(a + Math.PI / 2) * w)];
    out.push(
      <g key={i}>
        <path d={`M 0 0 L ${l[0]} ${l[1]} L ${tip[0]} ${tip[1]} Z`} fill={PAPER_HI}
              stroke={INK} strokeWidth={0.9} strokeLinejoin="round" />
        <path d={`M 0 0 L ${r[0]} ${r[1]} L ${tip[0]} ${tip[1]} Z`} fill={INK}
              fillOpacity={0.82} stroke={INK} strokeWidth={0.9} strokeLinejoin="round" />
      </g>
    );
  }
  return out;
}

export default function CompassRose({
  selected, onSelect, onRandom, spinning,
}: {
  selected: Power | null;
  onSelect: (p: Power) => void;
  onRandom: () => void;
  spinning: boolean;
}) {
  const needle = selected ? BEARING[selected] : -32;

  return (
    <svg viewBox="-320 -320 640 640" width="100%" height="100%"
         style={{ display: "block", width: "100%", height: "100%" }}>
      <defs>
        <radialGradient id="roseGlow" cx="50%" cy="50%" r="50%">
          <stop offset="60%" stopColor="#c9a227" stopOpacity="0" />
          <stop offset="100%" stopColor="#8a6414" stopOpacity="0.16" />
        </radialGradient>
      </defs>

      <circle r={RING + 46} fill="url(#roseGlow)" />

      {/* degree ring */}
      <circle r={R + 20} fill="none" stroke={INK} strokeWidth={1.4} strokeOpacity={0.55} />
      <circle r={R + 27} fill="none" stroke={INK} strokeWidth={0.8} strokeOpacity={0.35} />
      {Array.from({ length: 72 }, (_, i) => {
        const a = (i * 5 - 90) * (Math.PI / 180);
        const long = i % 6 === 0;
        return (
          <line key={i} x1={n(Math.cos(a) * (R + 20))} y1={n(Math.sin(a) * (R + 20))}
                x2={n(Math.cos(a) * (R + (long ? 27 : 24)))} y2={n(Math.sin(a) * (R + (long ? 27 : 24)))}
                stroke={INK} strokeWidth={long ? 1.4 : 0.7} strokeOpacity={0.5} />
        );
      })}

      {points()}
      <circle r={20} fill={PAPER_HI} stroke={INK} strokeWidth={1.6} />

      {/* the needle swings to your choice */}
      <g style={{ transform: `rotate(${needle}deg)`,
                  transition: spinning ? "transform 1.15s cubic-bezier(.16,.9,.28,1)"
                                       : "transform .55s cubic-bezier(.22,1,.36,1)" }}>
        <path d={`M 0 ${-R - 6} L 11 0 L 0 26 L -11 0 Z`} fill="#8f3328"
              stroke={INK} strokeWidth={1.4} strokeLinejoin="round" />
        <path d={`M 0 26 L 6 44 L -6 44 Z`} fill={INK} fillOpacity={0.7} />
        <circle r={7} fill={PAPER_HI} stroke={INK} strokeWidth={1.6} />
      </g>

      {/* The hub is the random pick. It carries no label because anything drawn
          here disappears under the rose; the instruction sits in the page copy. */}
      <g onClick={onRandom} style={{ cursor: "pointer" }}>
        <title>Let fortune decide</title>
        <circle r={54} fill="transparent" />
      </g>

      {/* the seven seats, at their bearings */}
      {POWERS.map((p) => {
        const a = (BEARING[p] - 90) * (Math.PI / 180);
        const x = n(Math.cos(a) * RING), y = n(Math.sin(a) * RING);
        const on = selected === p;
        return (
          <g key={p} transform={`translate(${x} ${y})`} onClick={() => onSelect(p)}
             style={{ cursor: "pointer" }}>
            <title>{p[0] + p.slice(1).toLowerCase()}</title>
            {on && <circle r={38} fill={TOKEN[p]} fillOpacity={0.18} stroke={TOKEN[p]} strokeWidth={2.4} />}
            {/* a shield, not a rounded chip */}
            <path d="M -21 -23 L 21 -23 L 21 8 Q 21 24 0 32 Q -21 24 -21 8 Z"
                  fill={FILL[p]} stroke={BORDER_INK} strokeWidth={on ? 3 : 2}
                  strokeLinejoin="round" />
            <text y={4} textAnchor="middle" fontFamily="var(--font-chart), Georgia, serif"
                  fontSize={17} letterSpacing={1.2} fill="#fdfaf2">{p.slice(0, 3)}</text>
          </g>
        );
      })}
    </svg>
  );
}
