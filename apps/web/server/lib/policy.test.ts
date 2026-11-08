// Run: pnpm --filter web test
import assert from "node:assert/strict";
import { test } from "node:test";
import { decide, decideAll, judgeTyping, thresholds, type TrustInput } from "./policy";

const base: TrustInput = { risk: 0.1, windows: 10, profileActive: true, stepUpActive: false };

test("low risk allows every tier", () => {
  assert.deepEqual(decideAll(base), { view: "allow", standard: "allow", elevated: "allow", critical: "allow" });
});

test("thresholds per tier (7.4 defaults)", () => {
  assert.equal(decide({ ...base, risk: 0.4 }, "critical"), "step_up");
  assert.equal(decide({ ...base, risk: 0.4 }, "elevated"), "allow");
  assert.equal(decide({ ...base, risk: 0.85 }, "critical"), "deny");
  assert.equal(decide({ ...base, risk: 0.85 }, "elevated"), "step_up");
  assert.equal(decide({ ...base, risk: 0.99 }, "standard"), "deny");
  assert.equal(decide({ ...base, risk: 1 }, "view"), "allow");
});

test("ML down or too few windows forces step-up on elevated/critical, never deny", () => {
  for (const input of [{ ...base, risk: null }, { ...base, windows: 2 }]) {
    assert.deepEqual(decideAll(input), { view: "allow", standard: "allow", elevated: "step_up", critical: "step_up" });
  }
});

test("recent step-up skips step-up but not deny", () => {
  assert.equal(decide({ ...base, risk: 0.6, stepUpActive: true }, "critical"), "allow");
  assert.equal(decide({ ...base, risk: 0.85, stepUpActive: true }, "critical"), "deny");
  assert.equal(decide({ ...base, risk: 0.85, stepUpActive: true }, "elevated"), "allow");
  assert.equal(decide({ ...base, windows: 0, stepUpActive: true }, "critical"), "allow"); // unknown risk never denies
});

test("no profile: recent step-up allows critical", () => {
  assert.equal(decide({ ...base, profileActive: false, stepUpActive: true }, "critical"), "allow");
});

test("no active profile: step-up for critical only", () => {
  assert.deepEqual(decideAll({ ...base, risk: 0.99, profileActive: false }), {
    view: "allow", standard: "allow", elevated: "allow", critical: "step_up",
  });
});

test("POLICY_THRESHOLDS_JSON overrides a subset; bad JSON keeps defaults", () => {
  const t = thresholds('{"critical":{"stepUp":0.2},"elevated":{"deny":"x"}}');
  assert.equal(t.critical.stepUp, 0.2);
  assert.equal(t.critical.deny, 0.8);
  assert.equal(t.elevated.deny, 0.9);
  assert.equal(decide({ ...base, risk: 0.25 }, "critical", t), "step_up");
  assert.deepEqual(thresholds("{nope"), thresholds(""));
});

test("step-up typing: skip without a keys model or ML, retry until typed, fail on foreign typing", () => {
  const r = { keysModeled: true, started: true, windows: 2, risk: 0.2 };
  assert.equal(judgeTyping(null), "skip");
  assert.equal(judgeTyping({ ...r, keysModeled: false }), "skip");
  assert.equal(judgeTyping({ ...r, started: false, windows: 0, risk: null }), "retry");
  assert.equal(judgeTyping({ ...r, windows: 0, risk: null }), "retry");
  assert.equal(judgeTyping(r), "pass");
  assert.equal(judgeTyping({ ...r, risk: 0.5 }), "fail");
});
