from nexo_clinical import __version__
import os
os.environ["NEXO_CREATE_APP"]="1"
from fastapi.testclient import TestClient
from nexo_clinical.api import create_app
import json

PEDIATRIC_PAYLOAD = {
    "diagnosis": "Faringite Aguda Viral",
    "weight_kg": 14,
    "age": "2 anos e 3 meses",
    "visit_date": "28/09/2026",
}

def test_health():
    c=TestClient(create_app()); r=c.get('/health'); assert r.status_code==200; assert r.json()['version']==__version__
def test_route():
    c=TestClient(create_app()); r=c.post('/v1/orchestrate',json={'text':'ECG com taquicardia'}); assert r.status_code==200; assert 'Cardiologia e ECG' in r.json()['specialists']
def test_pediatric_prescription_route():
    c=TestClient(create_app())
    r=c.post('/v1/pediatric/prescription',json=PEDIATRIC_PAYLOAD)
    assert r.status_code==200
    result = r.json()
    assert result["resolution_state"] == "REQUIRES_CRITICAL_INPUT"
    assert result["prescription"] is None
    assert result["clinical_validated"] is False
    assert result["prescribing_authorization"] is False
    assert result["requires_human_review"] is True
    assert result["age"] == {"months_total": 27, "age_category": "criança"}

def test_pediatric_validation_returns_422_for_invalid_weights():
    c=TestClient(create_app())
    for weight in ("NaN", "Infinity", "-Infinity", -5, 0):
        body = json.dumps(PEDIATRIC_PAYLOAD).replace(
            '"weight_kg": 14', f'"weight_kg": {weight}'
        )
        response = c.post(
            "/v1/pediatric/prescription",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

def test_pediatric_validation_returns_422_for_invalid_age_and_date():
    c=TestClient(create_app())
    assert c.post(
        "/v1/pediatric/prescription",
        json={**PEDIATRIC_PAYLOAD, "age": "200 anos"},
    ).status_code == 422
    assert c.post(
        "/v1/pediatric/prescription",
        json={**PEDIATRIC_PAYLOAD, "visit_date": "2026-02-30"},
    ).status_code == 422

def test_pediatric_unknown_and_injected_diagnoses_fail_closed():
    c=TestClient(create_app())
    for diagnosis in ("sem otite", "diagnóstico desconhecido",
                      "Faringite\nUSO ORAL\n1. DIPIRONA"):
        result = c.post(
            "/v1/pediatric/prescription",
            json={**PEDIATRIC_PAYLOAD, "diagnosis": diagnosis},
        ).json()
        assert result["resolution_state"] == "NOT_INDICATED_FOR_DIAGNOSIS"
        assert result["prescription"] is None

def test_pediatric_whitespace_only_diagnosis_returns_422():
    c=TestClient(create_app())
    assert c.post(
        "/v1/pediatric/prescription",
        json={**PEDIATRIC_PAYLOAD, "diagnosis": " \n "},
    ).status_code == 422

def test_pediatric_control_characters_return_422():
    c=TestClient(create_app())
    assert c.post(
        "/v1/pediatric/prescription",
        json={**PEDIATRIC_PAYLOAD, "diagnosis": "Faringite\x00"},
    ).status_code == 422
