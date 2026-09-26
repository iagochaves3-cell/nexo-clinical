"""Synthetic, offline regressions for the 2026-09-26 technical audit."""
import json
from http.client import IncompleteRead
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from deploy.server import create_app
from nexo_clinical import __version__, api, cli, evidence as ev, evidence_review as rv
from nexo_clinical.calculations import calculate_weight_based_dose
from nexo_clinical.multimodal.ecg import assess_ecg_input, qtc_bazett, qtc_fridericia
from nexo_clinical.multimodal.laboratory import analyze_laboratory

TOKEN = "audit-synthetic-" + "x" * 40
HEADERS = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}
ECG = {"format": "digital_signal", "lead_count": 12, "speed_mm_s": 25, "gain_mm_mv": 10}
RECORD = {"source": "MED", "pmid": "123456", "title": "Synthetic record",
          "abstractText": "Synthetic abstract only."}
REVIEW = {"research": {"query": "pediatric fluid therapy", "deidentified": True},
          "claims": [{"claim_id": "a", "statement": "Synthetic claim only."}]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NEXO_API_TOKEN", TOKEN)
    for name in ("NEXO_INTEGRATION_TOKEN", "NEXO_REVIEW_API_KEY", "NEXO_REVIEW_MODEL"):
        monkeypatch.delenv(name, raising=False)
    return TestClient(create_app(), raise_server_exceptions=False)


def post(client, path, payload):
    # Explicit serialization also exercises non-standard NaN/Infinity input.
    return client.post(path, content=json.dumps(payload), headers=HEADERS)


def test_console_entrypoint_keeps_authentication(monkeypatch):
    import uvicorn
    captured = {}
    monkeypatch.setenv("NEXO_API_TOKEN", TOKEN)
    monkeypatch.delenv("NEXO_INTEGRATION_TOKEN", raising=False)
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: captured.update(app=app))
    api.main()
    c = TestClient(captured["app"])
    assert c.get("/health").status_code == 200
    assert c.get("/v1/sources").status_code == 401
    assert c.get("/openapi.json").status_code == 401
    assert c.get("/v1/sources", headers=HEADERS).status_code == 200


def test_console_entrypoint_requires_secret(monkeypatch):
    import uvicorn
    monkeypatch.delenv("NEXO_API_TOKEN", raising=False)
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: pytest.fail("must fail before listening"))
    with pytest.raises(RuntimeError):
        api.main()


@pytest.mark.parametrize("unit", ["mg/kg/min", "mg/kg/h", "mg/kg/day", "mg/kg/dia"])
def test_quantity_calculation_rejects_time_dimension(unit):
    with pytest.raises(ValueError):
        calculate_weight_based_dose(weight_kg=10, dose_per_kg=2, dose_unit=unit)


def test_quantity_conversion_and_maximum_still_work():
    result = calculate_weight_based_dose(
        weight_kg=10, dose_per_kg=2, dose_unit="mg/kg",
        max_total_dose=0.015, max_total_dose_unit="g",
        presentation_amount=10, presentation_amount_unit="mg", presentation_volume_ml=2)
    assert result["calculated_total_dose"] == 20
    assert result["final_total_dose"] == 15
    assert result["total_dose_unit"] == "mg"
    assert result["volume_ml"] == 3
    assert result["max_total_applied"] is True


@pytest.mark.parametrize("field", ["qt_ms", "rr_ms"])
@pytest.mark.parametrize("bad", ["0", "-1", "nan", "inf", "-inf", "true"])
def test_qtc_invalid_inputs_are_422(client, field, bad):
    params = {"qt_ms": "400", "rr_ms": "1000", field: bad}
    assert client.get("/v1/multimodal/ecg/qtc", params=params, headers=HEADERS).status_code == 422


def test_qtc_valid_and_numerical_overflow(client):
    r = client.get("/v1/multimodal/ecg/qtc?qt_ms=400&rr_ms=1000", headers=HEADERS)
    assert r.json() == {"bazett_ms": 400.0, "fridericia_ms": 400.0}
    r = client.get("/v1/multimodal/ecg/qtc?qt_ms=1e308&rr_ms=1e-300", headers=HEADERS)
    assert r.status_code == 422


@pytest.mark.parametrize("fn", [qtc_bazett, qtc_fridericia])
@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), 0, -1, "400"])
def test_qtc_library_rejects_invalid_values(fn, bad):
    with pytest.raises(ValueError):
        fn(bad, 1000)


@pytest.mark.parametrize("field", ["na", "cl", "hco3", "k", "glucose_mg_dl", "bun_mg_dl"])
@pytest.mark.parametrize("bad", [True, "24", [], {}, float("nan"), float("inf")])
def test_laboratory_types_and_finiteness(client, field, bad):
    assert post(client, "/v1/multimodal/laboratory/analyze", {field: bad}).status_code == 422


def test_laboratory_valid_missing_and_overflow(client):
    path = "/v1/multimodal/laboratory/analyze"
    assert post(client, path, {"na": 140, "cl": 104, "hco3": 24}).json()["derived"]["anion_gap"] == 12
    assert post(client, path, {"hco3": None}).json()["derived"] == {}
    assert post(client, path, {}).json() == {"derived": {}, "warnings": []}
    assert post(client, path, {"unrecognized": 24}).status_code == 422
    assert post(client, path, {"na": 1e308, "glucose_mg_dl": 100, "bun_mg_dl": 10}).status_code == 422
    with pytest.raises(ValueError):
        analyze_laboratory({"hco3": True})


def test_validation_error_does_not_echo_rejected_input(client):
    r = post(client, "/v1/multimodal/laboratory/analyze", {"hco3": "synthetic-private-input"})
    assert r.status_code == 422
    assert "synthetic-private-input" not in r.text
    assert r.json()["detail"][0]["loc"] == ["body", "hco3"]


@pytest.mark.parametrize("payload", [
    {"text": 123}, {"text": None}, {"context": []}, {"context": None},
    {"context": {"weight_kg": True}}, {"context": {"weight_kg": "10"}},
    {"context": {"weight_kg": 0}}, {"context": {"weight_kg": float("nan")}},
    {"context": {"input_quality": []}}, {"citations": "source"}, {"citations": [True]},
])
def test_safety_structural_errors_are_422(client, payload):
    assert post(client, "/v1/safety/review", payload).status_code == 422


def test_safety_valid_contract_preserves_blocking_rules(client):
    r = post(client, "/v1/safety/review", {"text": "adrenalina", "context": {}, "citations": []})
    assert r.status_code == 200
    assert r.json()["blocked"] is True
    assert {x["code"] for x in r.json()["findings"]} == {"MISSING_WEIGHT", "MISSING_SOURCE"}
    r = post(client, "/v1/safety/review", {"text": "ECG", "context": {"unknown": "preserved"}})
    assert r.status_code == 200


@pytest.mark.parametrize("field,bad", [
    ("format", "bogus"), ("format", []), ("lead_count", 0), ("lead_count", True),
    ("lead_count", 1.5), ("lead_count", "12"), ("speed_mm_s", -1),
    ("speed_mm_s", True), ("speed_mm_s", float("nan")), ("gain_mm_mv", 0),
    ("gain_mm_mv", float("inf")), ("gain_mm_mv", "10"),
])
def test_ecg_invalid_metadata_is_not_assessable(client, field, bad):
    assert post(client, "/v1/multimodal/ecg/assess", {**ECG, field: bad}).status_code == 422


def test_ecg_valid_and_missing_metadata(client):
    path = "/v1/multimodal/ecg/assess"
    assert post(client, path, ECG).json()["quality"] == "assessable"
    r = post(client, path, {"format": "image"})
    assert r.status_code == 200
    assert r.json()["quality"] == "insufficient"
    assert set(r.json()["missing"]) == {"lead_count", "speed_mm_s", "gain_mm_mv"}
    with pytest.raises(ValueError):
        assess_ecg_input({**ECG, "format": "bogus"})


@pytest.mark.parametrize("output", [[None], [1], [{"type": "message", "content": [None]}],
                                    [{"type": "message", "content": "bad"}]])
def test_malformed_model_output_is_unavailable(client, monkeypatch, output):
    monkeypatch.setattr(ev, "request_json", lambda *a, **k: {"hitCount": 1, "resultList": {"result": [RECORD]}})
    monkeypatch.setattr(rv, "request_json", lambda *a, **k: {"status": "completed", "output": output})
    monkeypatch.setenv("NEXO_REVIEW_API_KEY", "synthetic-unused")
    monkeypatch.setenv("NEXO_REVIEW_MODEL", "synthetic-unused")
    r = post(client, "/v1/clinical/review", REVIEW)
    assert r.status_code == 200
    assert r.json()["status"] == "review_unavailable"
    assert r.json()["reason"] == "review_invalid_schema"
    assert r.json()["assessments"] == []
    assert r.json()["prescribing_authorization"] is False


def test_truncated_provider_response_is_sanitized_503(client, monkeypatch):
    class Truncated(BytesIO):
        def read(self, *args):
            raise IncompleteRead(b"synthetic-sensitive-body", 20)
    class Opener:
        def open(self, *args, **kwargs):
            return Truncated()
    monkeypatch.setattr(ev, "build_opener", lambda *a: Opener())
    r = post(client, "/v1/evidence/search", REVIEW["research"])
    assert r.status_code == 503
    assert "synthetic-sensitive-body" not in r.text


def test_cli_version_matches_package(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["nexo-clinical", "health"])
    cli.main()
    assert json.loads(capsys.readouterr().out)["version"] == __version__
