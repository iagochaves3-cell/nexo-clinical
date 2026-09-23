"""Server-only adapter shared by the three migrated documentary services.

Canonical source: nexo-clinical/integrations/nexo_client.py.
The upstream is centralized; this file does not duplicate medical rules.
"""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

ORIGIN = "https://nexo-clinical-api-production.up.railway.app"
PATHS = frozenset({"/v1/evidence/search", "/v1/clinical/review"})
DOMAINS = frozenset({"prescription", "fluid_therapy", "mechanical_ventilation"})
MAX_BODY_BYTES = 65_536
MAX_RESPONSE_BYTES = 2_000_000


class AdapterError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configured():
    return bool(os.environ.get("NEXO_API_URL", "").rstrip("/") == ORIGIN and
                re.fullmatch(r"[A-Za-z0-9_-]{32,256}", os.environ.get("NEXO_INTEGRATION_TOKEN", "")))


def forward(path, payload, domain):
    if path not in PATHS or domain not in DOMAINS:
        raise AdapterError(400, "unsupported_operation")
    if not isinstance(payload, dict):
        raise AdapterError(422, "invalid_payload")
    allowed = {"query", "deidentified", "limit"} if path.endswith("/search") else {"research", "patient_context", "claims", "domain"}
    if set(payload) - allowed:
        raise AdapterError(422, "unknown_fields")
    research = payload if path.endswith("/search") else payload.get("research", {})
    if not isinstance(research, dict) or research.get("deidentified") is not True:
        raise AdapterError(422, "deidentification_required")
    # Exact clinical validation, PHI checks and schemas remain centralized upstream.
    context = payload.get("patient_context", {})
    if not isinstance(context, dict) or set(context) - {"age_months", "weight_kg", "allergies", "renal_impairment", "hepatic_impairment"}:
        raise AdapterError(422, "invalid_patient_context")
    if not configured():
        raise AdapterError(503, "nexo_not_configured")
    outgoing = dict(payload)
    if path.endswith("/review"):
        outgoing["domain"] = domain
    try:
        body = json.dumps(outgoing, ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, TypeError):
        raise AdapterError(422, "invalid_json") from None
    if len(body) > MAX_BODY_BYTES:
        raise AdapterError(413, "body_too_large")
    request = Request(ORIGIN + path, data=body, headers={
        "Authorization": "Bearer " + os.environ["NEXO_INTEGRATION_TOKEN"],
        "Content-Type": "application/json", "Accept": "application/json",
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=65) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise AdapterError(502, "nexo_response_too_large")
            result = json.loads(raw)
    except HTTPError as exc:
        # Do not forward upstream bodies (could echo credentials or clinical text).
        if exc.code == 422:
            raise AdapterError(422, "nexo_rejected_payload") from None
        if exc.code == 429:
            raise AdapterError(429, "nexo_capacity_exceeded") from None
        raise AdapterError(503, "nexo_unavailable") from None
    except (URLError, OSError, ValueError):
        raise AdapterError(503, "nexo_unavailable") from None
    if not isinstance(result, dict) or result.get("clinical_validated") is not False:
        raise AdapterError(502, "nexo_invalid_contract")
    if path.endswith("/review"):
        if result.get("status") not in {"review_draft", "review_unavailable", "insufficient_evidence"} or result.get("prescribing_authorization") is not False:
            raise AdapterError(502, "nexo_invalid_contract")
        if result.get("requires_human_review") is not True:
            raise AdapterError(502, "nexo_invalid_contract")
    elif not isinstance(result.get("sources"), list):
        raise AdapterError(502, "nexo_invalid_contract")
    return result
