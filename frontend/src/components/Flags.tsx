"use client";

import type { Power } from "@/lib/map";

/* Flags as they stood in 1901. The five tricolours are drawn here; the Union
   Flag and the Ottoman star-and-crescent are the public-domain constructions
   from Wikimedia Commons, which are exact where a hand-drawn approximation
   would not be. Each keeps its own proportions rather than being squashed into
   a common box. */

export const FLAG_RATIO: Record<Power, number> = {
  AUSTRIA: 1.5, ENGLAND: 2, FRANCE: 1.5, GERMANY: 1.5,
  ITALY: 1.5, RUSSIA: 1.5, TURKEY: 1.5,
};

const bandsH = (a: string, b: string, c: string) => (
  <>
    <rect width={60} height={13.34} fill={a} />
    <rect y={13.33} width={60} height={13.34} fill={b} />
    <rect y={26.66} width={60} height={13.34} fill={c} />
  </>
);
const bandsV = (a: string, b: string, c: string) => (
  <>
    <rect width={20} height={40} fill={a} />
    <rect x={20} width={20} height={40} fill={b} />
    <rect x={40} width={20} height={40} fill={c} />
  </>
);

export default function Flag({ power, height = 120 }: { power: Power; height?: number }) {
  const w = height * FLAG_RATIO[power];
  const common = {
    width: w, height, style: { display: "block" as const },
    role: "img" as const, "aria-label": `Flag of ${power[0] + power.slice(1).toLowerCase()}, 1901`,
  };

  if (power === "ENGLAND") {
    return (
      <svg viewBox="0 0 60 30" {...common}>
        <clipPath id="uk-edge"><path d="M0,0 v30 h60 v-30 z" /></clipPath>
        <clipPath id="uk-quarter">
          <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
        </clipPath>
        <g clipPath="url(#uk-edge)">
          <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
          <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth={6} />
          <path d="M0,0 L60,30 M60,0 L0,30" clipPath="url(#uk-quarter)" stroke="#C8102E" strokeWidth={4} />
          <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth={10} />
          <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth={6} />
        </g>
      </svg>
    );
  }

  if (power === "TURKEY") {
    return (
      <svg viewBox="0 0 60 40" {...common}>
        <g transform="scale(0.05)">
          <rect width={1200} height={800} fill="#E30A17" />
          <circle cx={425} cy={400} r={225} fill="#ffffff" />
          <circle cx={500} cy={400} r={180} fill="#E30A17" />
          <path fill="#FFFFFF" d="m 589.05959,400.5279 72.2995,-27.03457 3.36962,-77.11504 48.05317,60.40677 74.38203,-20.62517 -42.601,64.368 42.60101,64.368 -74.38204,-20.62516 -48.05316,60.40677 -3.36963,-77.11505 z" />
        </g>
      </svg>
    );
  }

  const field =
    power === "AUSTRIA" ? bandsH("#ED2939", "#ffffff", "#ED2939") :       // Austria-Hungary
    power === "GERMANY" ? bandsH("#000000", "#ffffff", "#DD0000") :       // German Empire
    power === "RUSSIA"  ? bandsH("#ffffff", "#0039A6", "#D52B1E") :       // Russian Empire
    power === "FRANCE"  ? bandsV("#002395", "#ffffff", "#ED2939") :
                          bandsV("#009246", "#ffffff", "#CE2B37");        // Kingdom of Italy

  return <svg viewBox="0 0 60 40" {...common}>{field}</svg>;
}
