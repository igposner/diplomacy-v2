/* Covers every order shape the board can produce, including the ones a given
   position may not offer (convoy, two-coast destinations). Run: npm run test:orders */
import assert from "node:assert/strict";
import { indexLegal, click, targets, type Entry } from "../src/lib/orderEntry.ts";

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
assert.equal(s.next.kind, "coast");
assert.deepEqual((s.next as { options: { dest: string }[] }).options.map((o) => o.dest).sort(),
                 ["SPA/NC", "SPA/SC"]); ok("two legal coasts prompt for a choice");

// highlights only ever offer legal targets
assert.deepEqual([...targets(ix, { kind: "unit", loc: "PAR" })].sort(), ["BUR", "PAR", "PIC"]);
assert.deepEqual([...targets(ix, { kind: "convoyInto", loc: "ENG", from: "LON" })].sort(), ["BEL", "BRE"]);
ok("highlights are exactly the legal targets");

console.log(`\n${n} checks passed`);
