import raw from "@/map/standard.json";

export type Kind = "land" | "sea" | "shut";
export type Power = "AUSTRIA" | "ENGLAND" | "FRANCE" | "GERMANY" | "ITALY" | "RUSSIA" | "TURKEY";

export interface Province {
  kind: Kind;
  locType: string | null;
  sc: boolean;
  home: Power | null;
  unit: [number, number] | null;
  dislodged: [number, number] | null;
  scDot: [number, number] | null;
  label: [number, number] | null;
  labelClearance: number;
  name: string;
  box: [number, number];
  coasts: string[];
}
export interface LayerShape { p: string | null; c: string; d: string }
export interface MapData {
  viewBox: [number, number, number, number];
  /** Frame derived from real content: labels, units, centres and every landmass. */
  viewBoxFit: [number, number, number, number];
  provinces: Record<string, Province>;
  coastAnchors: Record<string, { unit: [number, number]; dislodged?: [number, number] }>;
  layer: LayerShape[];
  homes: Record<Power, string[]>;
  startUnits: Record<Power, string[]>;
  startCenters: Record<Power, string[]>;
}
export const MAP = raw as unknown as MapData;

/* Vintage board palette. Muted-saturated fills over aged paper, brown-black ink.
   Power hues follow the reference: brown England, navy France, violet Russia,
   gold Turkey, terracotta Austria, olive Italy, warm grey Germany. */
export const FILL: Record<Power, string> = {
  AUSTRIA: "#cf6b5e", ENGLAND: "#8d6544", FRANCE: "#4d6ea8", GERMANY: "#8a8578",
  ITALY: "#7ba55f", RUSSIA: "#9d6fb8", TURKEY: "#dda945",
};
export const TOKEN: Record<Power, string> = {
  AUSTRIA: "#8f3328", ENGLAND: "#523a24", FRANCE: "#26406b", GERMANY: "#4d4a42",
  ITALY: "#42632c", RUSSIA: "#5d3873", TURKEY: "#8a6414",
};
export const SEA = "#b9d7e8";
export const SEA_DEEP = "#a6c9de";
export const NEUTRAL_LAND = "#e7dcc3";
export const UNPLAYABLE = "#cdc4ad";
export const BORDER_INK = "#3b3428";
export const LABEL_INK = "#2f2a20";
export const PARCHMENT = "#ddcfae";
export const PARCHMENT_DARK = "#c2b088";

/* Every province polygon in standard.svg is separated from its neighbours by a
   gap of 0 to 7 units, so the raw gaps make borders that vary from invisible to
   very thick. EXPAND past the widest gap, then draw a fixed-width rim just
   outside the expanded shape; drawing province by province means each boundary
   keeps exactly one rim, at one width. */
/* EXPAND only has to be >= the widest gap (7), not twice it: the neighbour's
   expanded fill just has to reach the rim sitting EXPAND/2 outside this province.
   Keeping it tight stops small provinces like Wales and Yorkshire bloating. */
export const EXPAND = 9;
export const RIM = 2.2;

/** "A PAR" / "F STP/SC" -> { kind, loc } */
export function splitUnit(u: string): { kind: "A" | "F"; loc: string } {
  const [kind, ...rest] = u.split(" ");
  return { kind: kind as "A" | "F", loc: rest.join(" ") };
}

/** Where a unit token sits. Coast variants have their own anchor. */
export function unitAnchor(loc: string): [number, number] | null {
  const coast = MAP.coastAnchors[loc];
  if (coast) return coast.unit;
  return MAP.provinces[loc.split("/")[0]]?.unit ?? null;
}
