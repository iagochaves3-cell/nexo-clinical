/** Server-only NEXO client for PPS's Worker; never import into a client bundle. */
export const NEXO_ORIGIN = "https://nexo-clinical-api-production.up.railway.app";

/** Caller must enforce authentication, authorization and rate limiting first. */
export async function nexoClinicalGuard(payload, env, fetchImpl = fetch) {
  const pending = (reason) => ({
    nexoAtivado: false, resultadoValidacao: "insuficiente", reason,
    clinical_validated: false, prescribing_authorization: false,
  });
  if (String(env.NEXO_API_URL ?? "").replace(/\/$/, "") !== NEXO_ORIGIN ||
      !/^[A-Za-z0-9_-]{32,256}$/.test(env.NEXO_INTEGRATION_TOKEN ?? "")) {
    return pending("nexo_not_configured");
  }
  if (!payload || payload.research?.deidentified !== true || !Array.isArray(payload.claims)) {
    return pending("invalid_payload");
  }
  if (Object.keys(payload).some((key) => !["research", "claims", "patient_context"].includes(key))) {
    return pending("unknown_fields");
  }
  const allowed = ["age_months", "weight_kg", "allergies", "renal_impairment", "hepatic_impairment"];
  const context = payload.patient_context ?? {};
  if (!context || typeof context !== "object" || Array.isArray(context) ||
      Object.keys(context).some((key) => !allowed.includes(key))) return pending("invalid_patient_context");
  try {
    const body = JSON.stringify({ ...payload, patient_context: context, domain: "prescription" });
    if (new TextEncoder().encode(body).length > 65536) return pending("body_too_large");
    const response = await fetchImpl(NEXO_ORIGIN + "/v1/clinical/review", {
      method: "POST", redirect: "error", signal: AbortSignal.timeout(65000),
      headers: { Authorization: "Bearer " + env.NEXO_INTEGRATION_TOKEN, "Content-Type": "application/json" },
      body,
    });
    if (!response.ok) return pending("nexo_unavailable");
    const text = await response.text();
    if (new TextEncoder().encode(text).length > 2_000_000) return pending("invalid_response");
    const review = JSON.parse(text);
    if (review?.clinical_validated !== false || review.prescribing_authorization !== false ||
        review.requires_human_review !== true ||
        !["review_draft", "review_unavailable", "insufficient_evidence"].includes(review.status) ||
        !/^[a-f0-9]{64}$/.test(review.input_sha256 ?? "")) return pending("invalid_response");
    return { nexoAtivado: true, resultadoValidacao: "insuficiente", review,
             clinical_validated: false, prescribing_authorization: false };
  } catch {
    return pending("nexo_unavailable");
  }
}
