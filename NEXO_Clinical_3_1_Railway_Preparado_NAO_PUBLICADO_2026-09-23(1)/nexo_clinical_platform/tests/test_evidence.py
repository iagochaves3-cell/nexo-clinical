"""Contract/security tests with synthetic records; not clinical validation."""
import copy
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from deploy.server import create_app
from nexo_clinical import evidence as ev
from nexo_clinical import evidence_review as rv

TOKEN = "test-only-primary-" + "a" * 40
SECONDARY = "test-only-integration-" + "b" * 40
RECORD = {"source": "MED", "pmid": "123456", "title": "Synthetic study",
          "abstractText": "<p>The study included adults only.</p>",
          "pubTypeList": {"pubType": ["Journal Article"]},
          "doi": "10.1234/synthetic", "firstPublicationDate": "2025-01-01"}
SEARCH = {"query": "amoxicillin pharyngitis", "deidentified": True, "limit": 3}
REVIEW = {"research": SEARCH, "patient_context": {"weight_kg": 16, "age_months": 48},
          "claims": [{"claim_id": "med1", "statement": "This study included children."}]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NEXO_API_TOKEN", TOKEN)
    monkeypatch.setenv("NEXO_INTEGRATION_TOKEN", SECONDARY)
    monkeypatch.delenv("NEXO_REVIEW_API_KEY", raising=False)
    monkeypatch.delenv("NEXO_REVIEW_MODEL", raising=False)
    monkeypatch.setattr(ev, "request_json", lambda *a, **k: {"hitCount": 1, "resultList": {"result": [copy.deepcopy(RECORD)]}})
    return TestClient(create_app())


def post(client, path, payload=SEARCH, token=TOKEN):
    return client.post(path, json=payload, headers={"Authorization": "Bearer " + token})


def test_search_has_verifiable_provenance(client):
    result = post(client, "/v1/evidence/search").json()
    source = result["sources"][0]
    assert source["url"] == "https://pubmed.ncbi.nlm.nih.gov/123456/"
    assert source["doi"] == "10.1234/synthetic"
    assert len(source["content_sha256"]) == 64
    assert source["retrieved_at"]
    assert source["abstract_available"] is True
    assert "abstract" not in source
    assert result["clinical_validated"] is False


@pytest.mark.parametrize("path,payload", [("/v1/evidence/search", SEARCH), ("/v1/clinical/review", REVIEW)])
def test_new_routes_are_protected(client, path, payload):
    assert client.post(path, json=payload).status_code == 401
    assert post(client, path, payload, "invalid").status_code == 401
    assert post(client, path, payload, SECONDARY).status_code == 200
    assert client.get("/openapi.json", headers={"Authorization": "Bearer " + SECONDARY}).status_code == 401
    assert post(client, "/v1/orchestrate", {"text": "ECG"}, SECONDARY).status_code == 401


@pytest.mark.parametrize("query", ["nome: Fulano", "CPF: 12345678901", "test@example.com", "http://localhost", "amoxi 12345678", "amoxi OR SRC:PPR", "peso 16"])
def test_identifiers_and_provider_syntax_rejected(client, query):
    response = post(client, "/v1/evidence/search", {**SEARCH, "query": query})
    assert response.status_code == 422


@pytest.mark.parametrize("payload", [{**SEARCH, "deidentified": False}, {"query": "amoxicillin"},
                                    {**SEARCH, "name": "Patient"}, {**SEARCH, "limit": 0},
                                    {**SEARCH, "limit": 11}, {**SEARCH, "limit": True}])
def test_search_invalid_contract(client, payload):
    assert post(client, "/v1/evidence/search", payload).status_code == 422


def test_query_excludes_patient_context(client, monkeypatch):
    urls = []
    def capture(url):
        urls.append(url)
        return {"hitCount": 0, "resultList": {"result": []}}
    monkeypatch.setattr(ev, "request_json", capture)
    result = post(client, "/v1/clinical/review", REVIEW).json()
    assert result["status"] == "insufficient_evidence"
    assert len(urls) == 1
    assert "weight" not in urls[0] and "16" not in urls[0] and "48" not in urls[0]


def test_unavailable_provider_never_fakes_review(client):
    result = post(client, "/v1/clinical/review", REVIEW).json()
    assert result["status"] == "review_unavailable"
    assert result["reason"] == "review_provider_not_configured"
    assert result["clinical_validated"] is False
    assert result["prescribing_authorization"] is False
    assert result["checks"]["mathematical"] == "not_executed"
    assert result["assessments"] == []
    assert result["research"]["sources"]


def test_upstream_failure_is_503_not_empty_success(client, monkeypatch):
    def fail(*a, **k):
        raise ev.ProviderUnavailable("upstream_request_failed")
    monkeypatch.setattr(ev, "request_json", fail)
    assert post(client, "/v1/evidence/search").status_code == 503
    assert post(client, "/v1/clinical/review", REVIEW).status_code == 503


@pytest.mark.parametrize("data", [{}, {"version": "6.9"}, {"hitCount": 1, "resultList": {"result": "bad"}}])
def test_malformed_200_is_not_search_success(client, monkeypatch, data):
    monkeypatch.setattr(ev, "request_json", lambda *a, **k: data)
    assert post(client, "/v1/evidence/search").status_code == 503


def test_retracted_and_duplicate_records_excluded(client, monkeypatch):
    withdrawn = {**RECORD, "pmid": "789", "pubTypeList": {"pubType": ["Retracted Publication"]}}
    monkeypatch.setattr(ev, "request_json", lambda *a, **k: {"hitCount": 3, "resultList": {"result": [RECORD, RECORD, withdrawn]}})
    assert len(post(client, "/v1/evidence/search").json()["sources"]) == 1


def fake_model(assessment):
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps({"assessments": [assessment]})}]}]}


ASSESSMENT = {"claim_id": "med1", "verdict": "conflicting", "rationale": "A amostra descrita é de adultos.",
              "citations": [{"source_id": "pubmed:123456", "quote": "The study included adults only."}],
              "missing_information": []}


def configure_model(monkeypatch, assessment):
    monkeypatch.setenv("NEXO_REVIEW_API_KEY", "synthetic-key-never-use")
    monkeypatch.setenv("NEXO_REVIEW_MODEL", "synthetic-model")
    def capture(url, **kwargs):
        assert url == ev.REVIEW_URL
        assert kwargs["payload"]["store"] is False
        assert kwargs["payload"]["text"]["format"]["strict"] is True
        return fake_model(assessment)
    monkeypatch.setattr(rv, "request_json", capture)


def test_grounded_draft_still_requires_human_review(client, monkeypatch):
    configure_model(monkeypatch, ASSESSMENT)
    result = post(client, "/v1/clinical/review", REVIEW).json()
    assert result["status"] == "review_draft"
    assert result["requires_human_review"] is True
    assert result["clinical_validated"] is False
    assert result["prescribing_authorization"] is False
    assert "synthetic-key" not in json.dumps(result)


@pytest.mark.parametrize("alteration", [{"claim_id": "wrong"}, {"citations": []},
                                      {"citations": [{"source_id": "invented", "quote": "The study included adults only."}]},
                                      {"citations": [{"source_id": "pubmed:123456", "quote": "Works in children"}]}])
def test_unsupported_model_output_is_discarded(client, monkeypatch, alteration):
    configure_model(monkeypatch, {**ASSESSMENT, **alteration})
    result = post(client, "/v1/clinical/review", REVIEW).json()
    assert result["status"] == "review_unavailable"
    assert result["assessments"] == []


@pytest.mark.parametrize("age,weight", [(2, 3), (12, 10), (48, 16)])
def test_pediatric_contract_preserves_unknowns(client, age, weight):
    payload = {**REVIEW, "patient_context": {"age_months": age, "weight_kg": weight}}
    result = post(client, "/v1/clinical/review", payload).json()
    assert result["status"] == "review_unavailable"
    assert rv.ReviewRequest.model_validate(payload).patient_context.allergies is None


def test_context_change_invalidates_fingerprint(client):
    first = post(client, "/v1/clinical/review", REVIEW).json()
    changed = {**REVIEW, "patient_context": {"weight_kg": 10, "age_months": 12}}
    second = post(client, "/v1/clinical/review", changed).json()
    assert first["input_sha256"] != second["input_sha256"]


def test_duplicate_claim_or_extra_context_rejected(client):
    assert post(client, "/v1/clinical/review", {**REVIEW, "claims": REVIEW["claims"] * 2}).status_code == 422
    assert post(client, "/v1/clinical/review", {**REVIEW, "patient_context": {"name": "Patient"}}).status_code == 422


def test_integration_secret_must_be_independent(client, monkeypatch):
    monkeypatch.setenv("NEXO_INTEGRATION_TOKEN", TOKEN)
    with pytest.raises(RuntimeError):
        create_app()


def test_arbitrary_upstream_or_key_destination_rejected():
    with pytest.raises(ev.ProviderUnavailable):
        ev.request_json("http://127.0.0.1/")
    with pytest.raises(ev.ProviderUnavailable):
        ev.request_json(ev.SEARCH_URL + "?query=test", token="secret")


@pytest.mark.parametrize("context", [{"weight_kg": True}, {"age_months": "2"}, {"weight_kg": -1},
                                     {"renal_impairment": "false"}, {"age_months": 217}])
def test_invalid_context_not_coerced_into_valid_patient(client, context):
    assert post(client, "/v1/clinical/review", {**REVIEW, "patient_context": context}).status_code == 422


def test_total_quote_limit_and_incomplete_model_rejected(client, monkeypatch):
    configure_model(monkeypatch, {**ASSESSMENT, "citations": ASSESSMENT["citations"] * 6})
    assert post(client, "/v1/clinical/review", REVIEW).json()["reason"] == "review_quote_limit"
    monkeypatch.setattr(rv, "request_json", lambda *a, **k: {"status": "incomplete", "output": []})
    assert post(client, "/v1/clinical/review", REVIEW).json()["reason"] == "review_incomplete"
