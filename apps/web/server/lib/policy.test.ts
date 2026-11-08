// Run: pnpm --filter web test
import assert from "node:assert/strict";
import { test } from "node:test";
import { coachingScore, decide, decideAll, judgeTyping, thresholds, type TrustInput } from "./policy";

const base: TrustInput = { risk: 0.1, windows: 10, profileActive: true, stepUpActive: false, coaching: 0, holdReleased: false };

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

const quiet = { pastes: 0, tabSwitches: 0, longPauses: 0, chunkedDigits: 0, navs: 10 };
const OLD = 60 * 60 * 1000;

test("coaching score: no signals is zero; signals add up with reasons; capped at 1", () => {
  assert.deepEqual(coachingScore(quiet, OLD), { score: 0, reasons: [] });
  assert.deepEqual(coachingScore(null, 0), { score: 0, reasons: [] });
  const one = coachingScore({ ...quiet, tabSwitches: 1 }, OLD);
  assert.equal(one.score, 0.3);
  const coached = coachingScore({ ...quiet, tabSwitches: 1, pastes: 1 }, OLD);
  assert.equal(coached.score, 0.6);
  assert.deepEqual(coached.reasons, ["left the page and came back 1x", "pasted into a field"]);
  assert.equal(coachingScore({ pastes: 2, tabSwitches: 5, longPauses: 3, chunkedDigits: 4, navs: 1 }, 0).score, 1);
});

test("coaching score: a fresh session going straight to the action counts; a browsed one does not", () => {
  assert.equal(coachingScore({ ...quiet, navs: 2 }, 60_000).score, 0.2);
  assert.equal(coachingScore({ ...quiet, navs: 3 }, 60_000).score, 0);
  assert.equal(coachingScore({ ...quiet, navs: 1 }, OLD).score, 0);
});

test("pause: critical only, needs no profile, beats a recent step-up, loses to deny, lifted by a released hold", () => {
  const coached = { ...base, coaching: 0.6 };
  assert.deepEqual(decideAll(coached), { view: "allow", standard: "allow", elevated: "allow", critical: "pause" });
  assert.equal(decide({ ...coached, profileActive: false }, "critical"), "pause");
  assert.equal(decide({ ...coached, stepUpActive: true }, "critical"), "pause");
  assert.equal(decide({ ...coached, risk: 0.85 }, "critical"), "deny");
  assert.equal(decide({ ...coached, holdReleased: true }, "critical"), "allow");
  assert.equal(decide({ ...base, coaching: 0.45 }, "critical"), "allow");
});
