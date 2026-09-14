"use client";

import { useRef } from "react";
import {
  MAP, FILL, TOKEN, SEA, SEA_DEEP, NEUTRAL_LAND, UNPLAYABLE, BORDER_INK, LABEL_INK,
  EXPAND, RIM, splitUnit, unitAnchor, type Power,
} from "@/lib/map";
import type { Entry, LegalIndex } from "@/lib/orderEntry";

export interface BoardState {
  powers: Record<string, { units: string[]; centers: string[]; homes: string[] }>;
  centerOwners: Record<string, string>;
}

const FIT = MAP.viewBoxFit.join(" ");
const base = (p: string) => p.split("/")[0];
const HILITE = "#8a6414";

/* ---------------------------------------------------------------- pieces */
function Token({ power, kind, x, y, selected }:
  { power: Power; kind: "A" | "F"; x: number; y: number; selected?: boolean }) {
  const body = TOKEN[power];
  const rim = "#f4ecd8";
  return (
    <g style={{ pointerEvents: "none" }}>
      {selected && <circle cx={x} cy={y} r={26} fill={HILITE} fillOpacity={0.25}
                           stroke={HILITE} strokeWidth={3} />}
      <ellipse cx={x} cy={y + 13} rx={15} ry={4.2} fill="#2b2419" fillOpacity={0.3} />
      {kind === "A" ? (
        <g fill={body} stroke={rim} strokeWidth={1.8} strokeLinejoin="round">
          <path d={`M ${x - 10} ${y - 1.5} L ${x - 6} ${y - 10} L ${x + 6} ${y - 10} L ${x + 10} ${y - 1.5} Z`} />
          <rect x={x - 14} y={y - 1.5} width={28} height={11} rx={3} />
          <path d={`M ${x + 3} ${y - 6} L ${x + 17} ${y - 9}`} stroke={rim} strokeWidth={2.6} strokeLinecap="round" />
          <circle cx={x - 7.5} cy={y + 9.5} r={3.4} />
          <circle cx={x + 7.5} cy={y + 9.5} r={3.4} />
        </g>
      ) : (
        <g fill={body} stroke={rim} strokeWidth={1.8} strokeLinejoin="round">
          <path d={`M ${x - 15} ${y + 1} L ${x + 15} ${y + 1} L ${x + 10} ${y + 11} L ${x - 11} ${y + 11} Z`} />
          <rect x={x - 8} y={y - 7} width={17} height={8} rx={1.8} />
          <path d={`M ${x + 2} ${y - 7} L ${x + 2} ${y - 16}`} stroke={rim} strokeWidth={2.4} strokeLinecap="round" />
          <path d={`M ${x - 5} ${y - 7} L ${x - 5} ${y - 13}`} stroke={rim} strokeWidth={2.4} strokeLinecap="round" />
        </g>
      )}
    </g>
  );
}

function Star({ x, y, r = 10.5 }: { x: number; y: number; r?: number }) {
  const pts = Array.from({ length: 10 }, (_, i) => {
    const a = -Math.PI / 2 + (i * Math.PI) / 5;
    const rr = i % 2 === 0 ? r : r * 0.44;
    return `${(x + rr * Math.cos(a)).toFixed(1)},${(y + rr * Math.sin(a)).toFixed(1)}`;
  }).join(" ");
  return <polygon points={pts} fill="#fdfaf2" stroke={BORDER_INK} strokeWidth={1.4} strokeLinejoin="round" />;
}

/* ------------------------------------------------------- drafted orders */
const OR = {
  move: /^[AF] ([A-Z]{3}(?:\/[A-Z]{2})?) - ([A-Z]{3}(?:\/[A-Z]{2})?)( VIA)?$/,
  supMove: /^[AF] ([A-Z]{3}(?:\/[A-Z]{2})?) S [AF] [A-Z]{3}(?:\/[A-Z]{2})? - ([A-Z]{3}(?:\/[A-Z]{2})?)$/,
  supHold: /^[AF] ([A-Z]{3}(?:\/[A-Z]{2})?) S [AF] ([A-Z]{3}(?:\/[A-Z]{2})?)$/,
  convoy: /^F ([A-Z]{3}(?:\/[A-Z]{2})?) C A ([A-Z]{3}(?:\/[A-Z]{2})?) - ([A-Z]{3}(?:\/[A-Z]{2})?)$/,
  hold: /^[AF] ([A-Z]{3}(?:\/[A-Z]{2})?) H$/,
};

function Arrow({ from, to, colour, dashed, hollow }:
  { from: [number, number]; to: [number, number]; colour: string; dashed?: boolean; hollow?: boolean }) {
  const [x0, y0] = from, [x1, y1] = to;
  const dx = x1 - x0, dy = y1 - y0;
  const L = Math.hypot(dx, dy) || 1;
  const a: [number, number] = [x0 + (dx / L) * 20, y0 + (dy / L) * 20];
  const b: [number, number] = [x1 - (dx / L) * 24, y1 - (dy / L) * 24];
  const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
  const H = 15, w = 0.42;
  const head = `M ${b[0]} ${b[1]} L ${b[0] - H * Math.cos(ang - w)} ${b[1] - H * Math.sin(ang - w)} ` +
               `L ${b[0] - H * Math.cos(ang + w)} ${b[1] - H * Math.sin(ang + w)} Z`;
  const d = `M ${a[0]} ${a[1]} L ${b[0]} ${b[1]}`;
  return (
    <g style={{ pointerEvents: "none" }}>
      <path d={d} fill="none" stroke="#fdfaf2" strokeWidth={8} strokeOpacity={0.85} strokeLinecap="round" />
      <path d={d} fill="none" stroke={colour} strokeWidth={4} strokeLinecap="round"
            strokeDasharray={dashed ? "10 7" : undefined} />
      <path d={head} fill={hollow ? "#fdfaf2" : colour} stroke={colour} strokeWidth={2.4} strokeLinejoin="round" />
    </g>
  );
}

function HoldRing({ at, colour }: { at: [number, number]; colour: string }) {
  const [x, y] = at, r = 22;
  const pts = Array.from({ length: 8 }, (_, k) => {
    const a = ((k * 45 - 22.5) * Math.PI) / 180;
    return `${(x + r * Math.cos(a)).toFixed(1)},${(y + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");
  return (
    <g style={{ pointerEvents: "none" }}>
      <polygon points={pts} fill="none" stroke="#fdfaf2" strokeWidth={7} strokeOpacity={0.85} />
      <polygon points={pts} fill="none" stroke={colour} strokeWidth={3.4} />
    </g>
  );
}

function DraftedOrder({ order, colour }: { order: string; colour: string }) {
  let m: RegExpMatchArray | null;
  const at = (p: string) => unitAnchor(p);
  if ((m = order.match(OR.hold))) {
    const a = at(m[1]);
    return a ? <HoldRing at={a} colour={colour} /> : null;
  }
  if ((m = order.match(OR.convoy))) {
    const f = at(m[1]), o = at(m[2]), d = at(m[3]);
    return f && o && d ? (
      <>
        <Arrow from={o} to={f} colour={colour} dashed />
        <Arrow from={f} to={d} colour={colour} dashed />
      </>
    ) : null;
  }
  if ((m = order.match(OR.supMove))) {
    const a = at(m[1]), b = at(m[2]);
    return a && b ? <Arrow from={a} to={b} colour={colour} hollow /> : null;
  }
  if ((m = order.match(OR.supHold))) {
    const a = at(m[1]), b = at(m[2]);
    return a && b ? <><Arrow from={a} to={b} colour={colour} hollow /><HoldRing at={b} colour={colour} /></> : null;
  }
  if ((m = order.match(OR.move))) {
    const a = at(m[1]), b = at(m[2]);
    return a && b ? <Arrow from={a} to={b} colour={colour} dashed={!!m[3]} /> : null;
  }
  return null;
}

/* Marks for the phase that just resolved: a cross where a move bounced, a
   strike through a unit that was dislodged. Drawn from the engine's own codes. */
function FailureMarks({ result }: { result: { order: string; outcomes: string[] }[] }) {
  const marks: React.ReactNode[] = [];
  result.forEach((o, i) => {
    const mv = o.order.match(OR.move);
    if (o.outcomes.includes("BOUNCE") && mv) {
      const a = unitAnchor(mv[2]);
      if (a) marks.push(
        <g key={`b-${i}`} style={{ pointerEvents: "none" }}>
          <circle cx={a[0]} cy={a[1]} r={17} fill="#fdfaf2" fillOpacity={0.9} />
          <path d={`M ${a[0] - 11} ${a[1] - 11} L ${a[0] + 11} ${a[1] + 11}
                    M ${a[0] + 11} ${a[1] - 11} L ${a[0] - 11} ${a[1] + 11}`}
                stroke="#8f3328" strokeWidth={5} strokeLinecap="round" />
        </g>
      );
    }
    if (o.outcomes.includes("DISLODGED")) {
      const loc = o.order.split(" ")[1];
      const a = unitAnchor(loc);
      if (a) marks.push(
        <path key={`d-${i}`} style={{ pointerEvents: "none" }}
              d={`M ${a[0] - 17} ${a[1] + 16} L ${a[0] + 17} ${a[1] - 16}`}
              stroke="#8f3328" strokeWidth={5} strokeLinecap="round" />
      );
    }
  });
  return <>{marks}</>;
}

/* ------------------------------------------------------------------ board */
export default function Board({
  state, me, ix, entry, highlights, orders, results, onProvince, viewBox = FIT,
}: {
  state: BoardState;
  me: Power;
  ix: LegalIndex | null;
  entry: Entry;
  highlights: Set<string>;
  orders: string[];
  results?: { order: string; outcomes: string[] }[] | null;
  onProvince: (p: string, phase: "down" | "up") => void;
  viewBox?: string;
}) {
  const pressed = useRef<string | null>(null);

  const owner: Record<string, string> = { ...state.centerOwners };
  for (const [power, p] of Object.entries(state.powers)) {
    for (const u of p.units) {
      const b = base(splitUnit(u).loc);
      if (!owner[b]) owner[b] = power;
    }
  }

  const colourOf = (cls: string, prov: string | null) => {
    if (cls === "water") return SEA;
    if (cls === "neutral") return UNPLAYABLE;
    if (cls === "impassable") return "url(#hatch)";
    const o = prov ? owner[base(prov)] : undefined;
    return o ? FILL[o as Power] : NEUTRAL_LAND;
  };

  const ordered = [
    ...MAP.layer.filter((s) => s.c === "water"),
    ...MAP.layer.filter((s) => s.c !== "water"),
  ];
  const selectedLoc = entry && "loc" in entry ? entry.loc : null;

  return (
    <svg viewBox={viewBox} width="100%" height="100%" preserveAspectRatio="xMidYMid meet"
         style={{ display: "block", touchAction: "none" }}>
      <defs>
        <pattern id="hatch" width="9" height="9" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <rect width="9" height="9" fill={UNPLAYABLE} />
          <path d="M0 0 V9" stroke={BORDER_INK} strokeWidth={2.2} strokeOpacity={0.5} />
        </pattern>
        <radialGradient id="vignette" cx="50%" cy="48%" r="72%">
          <stop offset="55%" stopColor="#000" stopOpacity="0" />
          <stop offset="100%" stopColor="#3a2f1c" stopOpacity="0.20" />
        </radialGradient>
      </defs>

      <rect x={0} y={0} width={MAP.viewBox[2]} height={MAP.viewBox[3]} fill={SEA_DEEP} />

      {ordered.map((s, i) => {
        const c = colourOf(s.c, s.p);
        return (
          <g key={i}>
            <path d={s.d} fill="none" stroke={BORDER_INK} strokeWidth={EXPAND + RIM * 2} strokeLinejoin="round" />
            <path d={s.d} fill={c} stroke={c} strokeWidth={EXPAND} strokeLinejoin="round" />
          </g>
        );
      })}

      {/* Where you may click next. */}
      {ordered.filter((s) => s.p && highlights.has(base(s.p))).map((s, i) => (
        <path key={`h-${i}`} d={s.d} fill={HILITE} fillOpacity={0.3}
              stroke={HILITE} strokeWidth={4} strokeDasharray="12 7"
              style={{ pointerEvents: "none" }} />
      ))}

      {Object.entries(MAP.provinces).map(([id, p]) =>
        p.sc && p.scDot ? (
          <g key={`sc-${id}`} style={{ pointerEvents: "none" }}>
            {p.home && <circle cx={p.scDot[0]} cy={p.scDot[1]} r={15} fill="none"
                               stroke={BORDER_INK} strokeWidth={1.4} strokeOpacity={0.5} />}
            <Star x={p.scDot[0]} y={p.scDot[1]} />
          </g>
        ) : null
      )}

      {Object.entries(MAP.provinces).map(([id, p]) =>
        p.label ? (
          <text key={`l-${id}`} x={p.label[0]} y={p.label[1]} textAnchor="middle"
                fontFamily="'EB Garamond', Georgia, serif" fontWeight={600}
                fontSize={25} letterSpacing={1.8} fill={LABEL_INK}
                fillOpacity={p.kind === "sea" ? 0.66 : 0.9}
                stroke={p.kind === "sea" ? SEA : "#f2e9d4"} strokeWidth={3.2} strokeOpacity={0.6}
                paintOrder="stroke" strokeLinejoin="round" style={{ pointerEvents: "none" }}>
            {id.split("/")[0]}
          </text>
        ) : null
      )}

      {orders.map((o, i) => <DraftedOrder key={`o-${i}`} order={o} colour={TOKEN[me]} />)}
      {results && results.length > 0 && <FailureMarks result={results} />}

      {Object.entries(state.powers).flatMap(([power, p]) =>
        p.units.map((u) => {
          const { kind, loc } = splitUnit(u);
          const a = unitAnchor(loc);
          return a ? (
            <Token key={`${power}-${u}`} power={power as Power} kind={kind} x={a[0]} y={a[1]}
                   selected={selectedLoc != null && base(selectedLoc) === base(loc)} />
          ) : null;
        })
      )}

      <rect x={0} y={0} width={MAP.viewBox[2]} height={MAP.viewBox[3]} fill="url(#vignette)"
            pointerEvents="none" />

      {/* Invisible hit targets on top, so clicks land on provinces not on labels. */}
      {ix && ordered.filter((s) => s.p).map((s, i) => (
        <path key={`hit-${i}`} d={s.d} fill="transparent" stroke="transparent"
              strokeWidth={EXPAND} data-province={base(s.p!)}
              style={{ cursor: ix.all.has(s.p!) || highlights.has(base(s.p!)) ? "pointer" : "default" }}
              onPointerDown={(ev) => { ev.preventDefault(); pressed.current = base(s.p!); onProvince(base(s.p!), "down"); }}
              onPointerUp={() => { onProvince(base(s.p!), "up"); pressed.current = null; }} />
      ))}
    </svg>
  );
}
