/* Order entry modelled on how the online clients actually work.
 *
 * Backstabbr:  move   = click the unit, then click the destination
 *              hold   = click the unit, then click it again
 *              support= click the unit, press S, then click the two tiles of the
 *                       move being supported (same tile twice for a support-hold)
 *              convoy = click the fleet, press C, then click origin and destination
 * webDiplomacy adds a running hint telling you what to click next, which is worth
 * copying; we show one under the board.
 *
 * Every option offered here is derived from the engine's own legal-order list, so
 * an illegal order cannot be constructed.
 */

export type UnitKind = "A" | "F";

export interface LegalIndex {
  /** loc -> the exact hold order string */
  hold: Map<string, string>;
  /** loc -> destination (with coast, e.g. "SPA/SC") -> order string */
  move: Map<string, Map<string, string>>;
  /** the same, but the "... VIA" form, which is what a convoyed army needs */
  moveVia: Map<string, Map<string, string>>;
  /** loc -> supported unit's loc -> order string */
  supportHold: Map<string, Map<string, string>>;
  /** loc -> supported unit's loc -> destination -> order string */
  supportMove: Map<string, Map<string, Map<string, string>>>;
  /** fleet loc -> army loc -> destination -> order string */
  convoy: Map<string, Map<string, Map<string, string>>>;
  /** retreat phase: dislodged loc -> destination -> order string */
  retreat: Map<string, Map<string, string>>;
  /** retreat or removal: loc -> the disband order */
  disband: Map<string, string>;
  /** adjustment: province -> what may be built there */
  build: Map<string, Choice[]>;
  /** adjustment: the waive order, when a build may be given up */
  waive: string | null;
  /** loc -> "A" | "F" */
  kind: Map<string, UnitKind>;
  /** loc -> every legal order there, for the panel's "other" list */
  all: Map<string, string[]>;
}

export interface Choice { label: string; order: string }

const RX = {
  retreat: /^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?) R ([A-Z]{3}(?:\/[A-Z]{2})?)$/,
  disband: /^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?) D$/,
  build: /^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?) B$/,
  hold: /^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?) H$/,
  move: /^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?) - ([A-Z]{3}(?:\/[A-Z]{2})?)( VIA)?$/,
  supMove: /^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?) S [AF] ([A-Z]{3}(?:\/[A-Z]{2})?) - ([A-Z]{3}(?:\/[A-Z]{2})?)$/,
  supHold: /^([AF]) ([A-Z]{3}(?:\/[A-Z]{2})?) S [AF] ([A-Z]{3}(?:\/[A-Z]{2})?)$/,
  convoy: /^F ([A-Z]{3}(?:\/[A-Z]{2})?) C A ([A-Z]{3}(?:\/[A-Z]{2})?) - ([A-Z]{3}(?:\/[A-Z]{2})?)$/,
};

function nest<K, V>(m: Map<K, V>, k: K, make: () => V): V {
  let v = m.get(k);
  if (!v) { v = make(); m.set(k, v); }
  return v;
}

export function indexLegal(legal: Record<string, string[]>): LegalIndex {
  const ix: LegalIndex = {
    hold: new Map(), move: new Map(), supportHold: new Map(),
    supportMove: new Map(), convoy: new Map(), kind: new Map(), all: new Map(),
    moveVia: new Map(), retreat: new Map(), disband: new Map(), build: new Map(), waive: null,
  };
  const COAST = { NC: "north coast", SC: "south coast", EC: "east coast", WC: "west coast" } as const;
  for (const [loc, orders] of Object.entries(legal)) {
    ix.all.set(loc, orders);
    for (const o of orders) {
      let m: RegExpMatchArray | null;
      if (o === "WAIVE") {
        ix.waive = o;
      } else if ((m = o.match(RX.retreat))) {
        ix.kind.set(m[2], m[1] as UnitKind);
        nest(ix.retreat, m[2], () => new Map()).set(m[3], o);
      } else if ((m = o.match(RX.disband))) {
        ix.kind.set(m[2], m[1] as UnitKind);
        ix.disband.set(m[2], o);
      } else if ((m = o.match(RX.build))) {
        const coast = m[2].includes("/") ? m[2].split("/")[1] : null;
        const label = (m[1] === "A" ? "Army" : "Fleet") +
          (coast ? ` (${COAST[coast as keyof typeof COAST] ?? coast})` : "");
        nest(ix.build, base(m[2]), () => []).push({ label, order: o });
      } else if ((m = o.match(RX.hold))) {
        ix.kind.set(m[2], m[1] as UnitKind);
        ix.hold.set(m[2], o);
      } else if ((m = o.match(RX.supMove))) {
        ix.kind.set(m[2], m[1] as UnitKind);
        nest(nest(ix.supportMove, m[2], () => new Map()), m[3], () => new Map()).set(m[4], o);
      } else if ((m = o.match(RX.supHold))) {
        ix.kind.set(m[2], m[1] as UnitKind);
        nest(ix.supportHold, m[2], () => new Map()).set(m[3], o);
      } else if ((m = o.match(RX.convoy))) {
        ix.kind.set(m[1], "F");
        nest(nest(ix.convoy, m[1], () => new Map()), m[2], () => new Map()).set(m[3], o);
      } else if ((m = o.match(RX.move))) {
        ix.kind.set(m[2], m[1] as UnitKind);
        // "A LON - BEL" and "A LON - BEL VIA" share a destination; keep the plain
        // one as the default and let the panel expose the convoy variant.
        if (m[4]) nest(ix.moveVia, m[2], () => new Map()).set(m[3], o);
        const dests = nest(ix.move, m[2], () => new Map());
        if (!dests.has(m[3]) || !m[4]) dests.set(m[3], o);
      }
    }
  }
  return ix;
}

export type Entry =
  | { kind: "idle" }
  | { kind: "unit"; loc: string }
  | { kind: "supportPick"; loc: string }
  | { kind: "supportInto"; loc: string; from: string }
  | { kind: "convoyPick"; loc: string }
  | { kind: "convoyInto"; loc: string; from: string }
  | { kind: "choice"; loc: string; prompt: string; options: Choice[] };

const base = (p: string) => p.split("/")[0];

/** Provinces that should light up as clickable in the current state. */
export function targets(ix: LegalIndex, e: Entry): Set<string> {
  const out = new Set<string>();
  if (!ix || !e) return out;
  const add = (p: string) => out.add(base(p));
  switch (e.kind) {
    case "idle":
      // Nothing stands on a buildable centre, so show where a build may go.
      ix.build.forEach((_v, loc) => add(loc));
      break;
    case "unit":
      ix.move.get(e.loc)?.forEach((_o, d) => add(d));
      ix.retreat.get(e.loc)?.forEach((_o, d) => add(d));
      if (ix.hold.has(e.loc)) add(e.loc);
      break;
    case "supportPick":
      ix.supportHold.get(e.loc)?.forEach((_o, t) => add(t));
      ix.supportMove.get(e.loc)?.forEach((_m, t) => add(t));
      break;
    case "supportInto":
      ix.supportMove.get(e.loc)?.get(e.from)?.forEach((_o, d) => add(d));
      if (ix.supportHold.get(e.loc)?.has(e.from)) add(e.from);
      break;
    case "convoyPick":
      ix.convoy.get(e.loc)?.forEach((_m, a) => add(a));
      break;
    case "convoyInto":
      ix.convoy.get(e.loc)?.get(e.from)?.forEach((_o, d) => add(d));
      break;
  }
  return out;
}

export interface Step {
  next: Entry;
  order?: string;
  /** A convoy needs two orders: the fleet carries, and the army moves VIA.
      PlayDiplomacy states it plainly -- order the army to the destination and
      every fleet on the path to convoy. Ordering only the fleet does nothing. */
  companion?: string;
}

const COAST_NAME: Record<string, string> = {
  NC: "north coast", SC: "south coast", EC: "east coast", WC: "west coast",
};
function coastPrompt(loc: string, dest: string, multi: { dest: string; order: string }[]): Entry {
  return {
    kind: "choice", loc, prompt: `${dest} has two coasts`,
    options: multi.map(({ dest: d, order }) => ({
      label: COAST_NAME[d.split("/")[1]] ?? d, order,
    })),
  };
}

export interface Mode { label: string; hint: string; next?: Entry; order?: string }

/** What the selected unit can be told to do, as buttons. Backstabbr hides these
    behind S and C; webDiplomacy shows them, which is how anyone discovers that a
    fleet in open sea can convoy at all. */
export function modes(ix: LegalIndex, e: Entry): Mode[] {
  if (!ix || !e || e.kind !== "unit") return [];
  const out: Mode[] = [];
  const h = ix.hold.get(e.loc);
  if (h) out.push({ label: "Hold", hint: "stay put", order: h });
  if (ix.move.has(e.loc)) out.push({ label: "Move", hint: "click a highlighted province" });
  if (ix.supportHold.has(e.loc) || ix.supportMove.has(e.loc))
    out.push({ label: "Support", hint: "back another unit", next: { kind: "supportPick", loc: e.loc } });
  if (ix.convoy.has(e.loc))
    out.push({ label: "Convoy", hint: "carry an army across water",
               next: { kind: "convoyPick", loc: e.loc } });
  if (ix.retreat.has(e.loc)) out.push({ label: "Retreat", hint: "click a highlighted province" });
  return out;
}

/** Terminal actions for the current state, shown as buttons beside the hint. */
export function chips(ix: LegalIndex, e: Entry): Choice[] {
  if (!ix || !e) return [];
  if (e.kind === "choice") return e.options;
  if (e.kind === "unit") {
    const d = ix.disband.get(e.loc);
    return d ? [{ label: "Disband", order: d }] : [];
  }
  if (e.kind === "idle" && ix.waive) return [{ label: "Waive a build", order: ix.waive }];
  return [];
}

/** One click on a province, resolved against the current state. */
export function click(ix: LegalIndex, e: Entry, p: string): Step {
  if (!ix || !e) return { next: { kind: "idle" } };
  const hit = (m: Map<string, string> | undefined) => {
    if (!m) return undefined;
    const exact = m.get(p);
    if (exact) return { dest: p, order: exact };
    const coastal = [...m.entries()].filter(([d]) => base(d) === p);
    if (coastal.length === 1) return { dest: coastal[0][0], order: coastal[0][1] };
    if (coastal.length > 1) return { multi: coastal.map(([dest, order]) => ({ dest, order })) };
    return undefined;
  };

  switch (e.kind) {
    case "idle": {
      const opts = ix.build.get(p);
      if (opts?.length)
        return { next: { kind: "choice", loc: p, prompt: `Build in ${p}`, options: opts } };
      const here = [...ix.all.keys()].find((l) => base(l) === p);
      return here ? { next: { kind: "unit", loc: here } } : { next: e };
    }

    case "unit": {
      if (p === base(e.loc)) {
        const h = ix.hold.get(e.loc);
        return h ? { next: { kind: "idle" }, order: h } : { next: e };
      }
      const rt = hit(ix.retreat.get(e.loc));
      if (rt && !("multi" in rt)) return { next: { kind: "idle" }, order: rt.order };
      const r = hit(ix.move.get(e.loc));
      if (r && "multi" in r) return { next: coastPrompt(e.loc, p, r.multi!) };
      if (r) return { next: { kind: "idle" }, order: r.order };
      const here = [...ix.all.keys()].find((l) => base(l) === p);
      return here ? { next: { kind: "unit", loc: here } } : { next: { kind: "idle" } };
    }

    case "supportPick": {
      const sm = ix.supportMove.get(e.loc);
      const sh = ix.supportHold.get(e.loc);
      const target = [...(sm?.keys() ?? []), ...(sh?.keys() ?? [])].find((t) => base(t) === p);
      return target ? { next: { kind: "supportInto", loc: e.loc, from: target } } : { next: e };
    }

    case "supportInto": {
      if (p === base(e.from)) {
        const o = ix.supportHold.get(e.loc)?.get(e.from);
        return o ? { next: { kind: "idle" }, order: o } : { next: e };
      }
      const r = hit(ix.supportMove.get(e.loc)?.get(e.from));
      if (r && "multi" in r) return { next: coastPrompt(e.loc, p, r.multi!) };
      if (r) return { next: { kind: "idle" }, order: r.order };
      return { next: e };
    }

    case "convoyPick": {
      const army = [...(ix.convoy.get(e.loc)?.keys() ?? [])].find((a) => base(a) === p);
      return army ? { next: { kind: "convoyInto", loc: e.loc, from: army } } : { next: e };
    }

    case "convoyInto": {
      const r = hit(ix.convoy.get(e.loc)?.get(e.from));
      if (r && !("multi" in r)) {
        // Order the army across too, when it is ours to order.
        const army = ix.moveVia.get(e.from)?.get(r.dest) ?? ix.move.get(e.from)?.get(r.dest);
        return { next: { kind: "idle" }, order: r.order, companion: army };
      }
      return { next: e };
    }

    default:
      return { next: e };
  }
}

/** The running instruction under the board, as webDiplomacy does. */
export function hint(ix: LegalIndex, e: Entry): string {
  if (!ix || !e) return "Loading\u2026";
  switch (e.kind) {
    case "idle":
      if (ix.build.size) return "Click a highlighted home centre to build there.";
      if (ix.disband.size && !ix.retreat.size) return "You are over strength. Click a unit to remove it.";
      if (ix.retreat.size) return "Click a dislodged unit to retreat it.";
      return "Click one of your units to order it.";
    case "unit":
      if (ix.retreat.has(e.loc))
        return `${e.loc} was dislodged. Click a highlighted province to retreat, or disband.`;
      if (ix.disband.has(e.loc) && !ix.hold.has(e.loc))
        return `${e.loc} selected. Disband it, or press Esc.`;
      return `${e.loc} selected. Click a highlighted province to move it, or choose below.`;
    case "supportPick":
      return `Supporting from ${e.loc}. Click the unit you are supporting.`;
    case "supportInto":
      return `Supporting ${e.from}. Click where it is going, or click ${base(e.from)} again to support it holding.`;
    case "convoyPick":
      return `Convoying with ${e.loc}. Click the army to carry.`;
    case "convoyInto":
      return `Carrying ${e.from}. Click where it lands.`;
    case "choice":
      return `${e.prompt}. Choose one.`;
  }
}
