import test from "node:test";
import assert from "node:assert/strict";
import { nexoClinicalGuard, NEXO_ORIGIN } from "./nexo-server.mjs";
import { createReviewState } from "./review-state.mjs";

const env = { NEXO_API_URL: NEXO_ORIGIN, NEXO_INTEGRATION_TOKEN: "test-only-" + "x".repeat(40) };
const payload = { research: { query: "amoxicillin pharyngitis", deidentified: true },
                  patient_context: { age_months: 48, weight_kg: 16 },
                  claims: [{ claim_id: "med1", statement: "Synthetic review claim" }] };
const upstream = { clinical_validated: false, prescribing_authorization: false,
                   requires_human_review: true, status: "review_draft", input_sha256: "a".repeat(64) };

test("missing configuration cannot approve", async () => {
  const r = await nexoClinicalGuard(payload, {}, () => assert.fail("must not call"));
  assert.equal(r.reason, "nexo_not_configured");
  assert.equal(r.prescribing_authorization, false);
});
test("server sends scoped secret only to fixed origin; no secret in response", async () => {
  const r = await nexoClinicalGuard(payload, env, async (url, init) => {
    assert.equal(url, NEXO_ORIGIN + "/v1/clinical/review");
    assert.equal(init.redirect, "error");
    assert.equal(init.headers.Authorization, "Bearer " + env.NEXO_INTEGRATION_TOKEN);
    assert.equal(JSON.parse(init.body).domain, "prescription");
    return Response.json(upstream);
  });
  assert.equal(r.nexoAtivado, true);
  assert.equal(r.resultadoValidacao, "insuficiente");
  assert.equal(JSON.stringify(r).includes(env.NEXO_INTEGRATION_TOKEN), false);
});
test("upstream errors and bogus clinical approval fail closed", async () => {
  for (const response of [Response.json({}, { status: 401 }), Response.json({}, { status: 503 }),
                          Response.json({ ...upstream, clinical_validated: true }), Response.json({})]) {
    const r = await nexoClinicalGuard(payload, env, async () => response);
    assert.equal(r.nexoAtivado, false);
    assert.equal(r.prescribing_authorization, false);
  }
});
test("identifiers and arbitrary origin cannot be forwarded", async () => {
  const noFetch = () => assert.fail("must not call");
  assert.equal((await nexoClinicalGuard({ ...payload, patient_context: { name: "Patient" } }, env, noFetch)).reason,
               "invalid_patient_context");
  assert.equal((await nexoClinicalGuard(payload, { ...env, NEXO_API_URL: "https://example.com" }, noFetch)).reason,
               "nexo_not_configured");
});
test("changed patient invalidates review and discards out-of-order responses", () => {
  const state = createReviewState();
  const first = state.invalidate();
  const second = state.invalidate();
  assert.equal(state.accept(first, upstream), false);
  assert.equal(state.snapshot().review, null);
  assert.equal(state.accept(second, upstream), true);
  state.invalidate();
  assert.equal(state.snapshot().review, null);
});
