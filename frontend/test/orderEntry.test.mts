/* Covers every order shape the board can produce, including the ones a given
   position may not offer (convoy, two-coast destinations). Run: npm run test:orders */
import assert from "node:assert/strict";
import { indexLegal, click, targets, chips, modes, type Entry } from "../src/lib/orderEntry.ts";

const legal = {
  PAR: ["A PAR H", "A PAR - BUR", "A PAR - PIC", "A PAR S A BUR", "A PAR S A BUR - MUN"],
  MAR: ["F MAR H", "F MAR - SPA/SC", "F MAR - LYO"],
  BRE: ["F BRE H", "F BRE - MAO", "F BRE - SPA/NC"],
  ENG: ["F ENG H", "F ENG C A LON - BEL", "F ENG C A LON - BRE"],
  // a fleet that can reach either coast of Spain
  POR: ["F POR H", "F POR - SPA/NC", "F POR - SPA/SC"],
};
const ix = indexLegal(legal);
const idle: Entry = { kind: "idle" };
let n = 0;
const ok = (label: string) => { n++; console.log("  ok", label); };

// select
let s = click(ix, idle, "PAR");
assert.deepEqual(s.next, { kind: "unit", loc: "PAR" });
assert.equal(s.order, undefined); ok("clicking a unit selects it, orders nothing");

// hold = click the same province again
s = click(ix, { kind: "unit", loc: "PAR" }, "PAR");
assert.equal(s.order, "A PAR H"); ok("second click on the unit orders a hold");

// move
s = click(ix, { kind: "unit", loc: "PAR" }, "BUR");
assert.equal(s.order, "A PAR - BUR"); ok("click a highlighted province orders a move");

// illegal destination is ignored, not invented
s = click(ix, { kind: "unit", loc: "PAR" }, "MUN");
assert.equal(s.order, undefined); ok("an illegal destination produces no order");

// support hold: S, click the unit, click it again
s = click(ix, { kind: "supportPick", loc: "PAR" }, "BUR");
assert.deepEqual(s.next, { kind: "supportInto", loc: "PAR", from: "BUR" });
s = click(ix, { kind: "supportInto", loc: "PAR", from: "BUR" }, "BUR");
assert.equal(s.order, "A PAR S A BUR"); ok("S then the same tile twice is a support-hold");

// support move: S, click the unit, click its destination
s = click(ix, { kind: "supportInto", loc: "PAR", from: "BUR" }, "MUN");
assert.equal(s.order, "A PAR S A BUR - MUN"); ok("S then two tiles is a support-move");

// convoy: C, click the army, click the landing
s = click(ix, { kind: "convoyPick", loc: "ENG" }, "LON");
assert.deepEqual(s.next, { kind: "convoyInto", loc: "ENG", from: "LON" });
s = click(ix, { kind: "convoyInto", loc: "ENG", from: "LON" }, "BEL");
assert.equal(s.order, "F ENG C A LON - BEL"); ok("C then origin and destination is a convoy");

// one legal coast: pick it silently
s = click(ix, { kind: "unit", loc: "MAR" }, "SPA");
assert.equal(s.order, "F MAR - SPA/SC"); ok("a single legal coast is chosen without asking");

// two legal coasts: ask
s = click(ix, { kind: "unit", loc: "POR" }, "SPA");
assert.equal(s.order, undefined);
assert.equal(s.next.kind, "choice");
assert.deepEqual((s.next as { options: { order: string }[] }).options.map((o) => o.order).sort(),
                 ["F POR - SPA/NC", "F POR - SPA/SC"]); ok("two legal coasts prompt for a choice");

// highlights only ever offer legal targets
assert.deepEqual([...targets(ix, { kind: "unit", loc: "PAR" })].sort(), ["BUR", "PAR", "PIC"]);
assert.deepEqual([...targets(ix, { kind: "convoyInto", loc: "ENG", from: "LON" })].sort(), ["BEL", "BRE"]);
ok("highlights are exactly the legal targets");

/* ---------------- retreat phase ---------------- */
const rIx = indexLegal({
  BUR: ["A BUR D", "A BUR R BEL", "A BUR R GAS", "A BUR R PAR"],
});
s = click(rIx, idle, "BUR");
assert.deepEqual(s.next, { kind: "unit", loc: "BUR" }); ok("a dislodged unit selects");
assert.deepEqual([...targets(rIx, { kind: "unit", loc: "BUR" })].sort(), ["BEL", "GAS", "PAR"]);
ok("retreat squares highlight, and only the legal ones");
s = click(rIx, { kind: "unit", loc: "BUR" }, "PAR");
assert.equal(s.order, "A BUR R PAR"); ok("clicking a retreat square orders the retreat");
s = click(rIx, { kind: "unit", loc: "BUR" }, "MUN");
assert.equal(s.order, undefined); ok("retreating into the attacker is not offered");
assert.deepEqual(chips(rIx, { kind: "unit", loc: "BUR" }), [{ label: "Disband", order: "A BUR D" }]);
ok("a dislodged unit offers disband");

/* ---------------- builds ---------------- */
const bIx = indexLegal({
  SEV: ["A SEV B", "F SEV B", "WAIVE"],
  STP: ["A STP B", "F STP/NC B", "F STP/SC B", "WAIVE"],
  WAR: ["A WAR B", "WAIVE"],
});
assert.deepEqual([...targets(bIx, idle)].sort(), ["SEV", "STP", "WAR"]);
ok("buildable home centres highlight with nothing selected");
s = click(bIx, idle, "WAR");
assert.equal(s.next.kind, "choice");
assert.deepEqual((s.next as { options: { label: string }[] }).options.map((o) => o.label), ["Army"]);
ok("an inland centre offers an army only");
s = click(bIx, idle, "SEV");
assert.deepEqual((s.next as { options: { label: string }[] }).options.map((o) => o.label),
                 ["Army", "Fleet"]); ok("a coastal centre offers both");
s = click(bIx, idle, "STP");
assert.deepEqual((s.next as { options: { label: string }[] }).options.map((o) => o.label),
                 ["Army", "Fleet (north coast)", "Fleet (south coast)"]);
ok("a two-coast centre names each coast");
assert.deepEqual(chips(bIx, idle), [{ label: "Waive a build", order: "WAIVE" }]);
ok("an unused build can be waived");
// regression: a buildable centre is also an orderable location, so a naive
// "select on press" hijacked it and showed the movement prompt instead.
assert.equal(click(bIx, idle, "SEV").next.kind, "choice");
assert.notEqual(click(bIx, idle, "SEV").next.kind, "unit");
ok("a buildable centre prompts to build, never selects as a unit");

/* ---------------- removals ---------------- */
const dIx = indexLegal({ CON: ["F CON D"], MOS: ["A MOS D"] });
s = click(dIx, idle, "CON");
assert.deepEqual(s.next, { kind: "unit", loc: "CON" });
assert.equal(s.order, undefined); ok("removing takes two steps, never one stray click");
assert.deepEqual(chips(dIx, { kind: "unit", loc: "CON" }), [{ label: "Disband", order: "F CON D" }]);
ok("a surplus unit offers disband");
assert.equal(chips(dIx, idle).length, 0); ok("no waive is offered when none is legal");

/* ---------------- a convoy orders both halves ---------------- */
const vIx = indexLegal({
  ENG: ["F ENG H", "F ENG C A PIC - BEL", "F ENG C A PIC - LON"],
  PIC: ["A PIC H", "A PIC - BEL", "A PIC - BEL VIA", "A PIC - BUR"],
});
s = click(vIx, { kind: "convoyInto", loc: "ENG", from: "PIC" }, "BEL");
assert.equal(s.order, "F ENG C A PIC - BEL");
assert.equal(s.companion, "A PIC - BEL VIA");
ok("a convoy orders the fleet to carry AND the army to go, by the VIA route");
// an army belonging to someone else is not ours to order
const wIx = indexLegal({ ENG: ["F ENG C A LON - BEL"] });
s = click(wIx, { kind: "convoyInto", loc: "ENG", from: "LON" }, "BEL");
assert.equal(s.order, "F ENG C A LON - BEL");
assert.equal(s.companion, undefined);
ok("convoying another power's army orders only our fleet");

/* ---------------- modes are discoverable, not hidden behind keys ------------- */
const cIx = indexLegal({
  ENG: ["F ENG H", "F ENG - MAO", "F ENG C A LON - BEL", "F ENG S F NTH"],
  PAR: ["A PAR H", "A PAR - BUR"],
});
assert.deepEqual(modes(cIx, { kind: "unit", loc: "ENG" }).map((m) => m.label),
                 ["Hold", "Move", "Support", "Convoy"]);
ok("a fleet that can convoy is offered a Convoy button");
assert.deepEqual(modes(cIx, { kind: "unit", loc: "PAR" }).map((m) => m.label), ["Hold", "Move"]);
ok("a unit that cannot convoy or support is not offered either");
assert.equal(modes(cIx, { kind: "unit", loc: "ENG" }).find((m) => m.label === "Convoy")!.next!.kind,
             "convoyPick");
ok("the Convoy button starts the convoy flow");
assert.deepEqual(modes(rIx, { kind: "unit", loc: "BUR" }).map((m) => m.label), ["Retreat"]);
ok("a dislodged unit is offered Retreat, not Move");
assert.deepEqual(modes(cIx, idle), []); ok("no modes with nothing selected");

console.log(`\n${n} checks passed`);
