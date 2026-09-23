"""Run inside a trusted terminal/server. Never prints credentials or response bodies.

NEXO_API_TOKEN must already exist in the environment. This script does not
prompt for, rotate, persist or send the token anywhere except the fixed API.
"""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE = "https://nexo-clinical-api-production.up.railway.app"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def call(path, token=None, payload=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(BASE + path, headers=headers,
                      data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with build_opener(NoRedirect()).open(request, timeout=65) as response:
            return response.status, json.loads(response.read(2_000_000))
    except HTTPError as exc:
        return exc.code, {}
    except (URLError, OSError, ValueError):
        return 0, {}


def main():
    failures = 0

    def report(name, passed):
        nonlocal failures
        failures += not passed
        print(json.dumps({"check": name, "passed": bool(passed)}))

    status, health = call("/health")
    report("public_health", status == 200 and health.get("status") == "ok")
    for path in ["/openapi.json", "/v1/sources", "/v1/capabilities"]:
        report("missing_token " + path, call(path)[0] == 401)
        report("invalid_token " + path, call(path, "synthetic-invalid-token")[0] == 401)
    token = os.environ.get("NEXO_API_TOKEN")
    if not token:
        print(json.dumps({"positive_auth": "not_executed", "reason": "NEXO_API_TOKEN_not_available"}))
        return 2
    status, data = call("/openapi.json", token)
    report("authenticated_openapi", status == 200 and "/v1/orchestrate" in data.get("paths", {}))
    status, data = call("/v1/sources", token)
    report("source_registry", status == 200 and isinstance(data, list) and len(data) > 0)
    status, data = call("/v1/orchestrate", token, {"text": "ECG com taquicardia; caso sintético"})
    report("specialist_routing", status == 200 and "Cardiologia e ECG" in data.get("specialists", []))
    status, data = call("/v1/safety/review", token, {"text": "adrenalina", "context": {}, "citations": []})
    report("missing_weight_safety", status == 200 and data.get("blocked") is True)
    status, data = call("/v1/multimodal/ecg/qtc?qt_ms=400&rr_ms=1000", token)
    report("qtc_synthetic_arithmetic", status == 200 and data.get("bazett_ms") == 400)
    if True:
        status, data = call("/v1/evidence/search", token,
                            {"query": "amoxicillin streptococcal pharyngitis", "deidentified": True, "limit": 2})
        report("live_evidence", status == 200 and bool(data.get("sources")) and data.get("clinical_validated") is False)
    scoped = os.environ.get("NEXO_INTEGRATION_TOKEN")
    report("integration_token_configured", bool(scoped))
    if scoped:
        status, data = call("/v1/capabilities", scoped)
        report("scoped_capabilities", status == 200 and data.get("live_evidence_search") is True)
        report("scoped_admin_denied", call("/openapi.json", scoped)[0] == 401)
        for age, weight in [(2, 3), (12, 10), (48, 16)]:
            status, data = call("/v1/clinical/review", scoped, {
                "research": {"query": "pediatric fluid therapy", "deidentified": True, "limit": 2},
                "patient_context": {"age_months": age, "weight_kg": weight},
                "claims": [{"claim_id": "synthetic", "statement": "Applicability to children requires review."}]
            })
            report("review_contract_" + str(age) + "m", status == 200 and
                   data.get("status") in {"review_unavailable", "insufficient_evidence", "review_draft"} and
                   data.get("clinical_validated") is False and data.get("prescribing_authorization") is False)
        report("patient_identifier_rejected", call("/v1/evidence/search", scoped, {
            "query": "nome: paciente sintetico", "deidentified": True})[0] == 422)
    print(json.dumps({"failures": failures, "clinical_validation": False}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
