from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from nexo_clinical.input_models import AgeInput, PediatricPrescriptionInput
from nexo_clinical.pediatric_pharmacotherapy import (
    RegimenEligibility,
    ResolutionState,
    diagnosis_linked_adjuncts,
    generate_pediatric_prescription,
    pediatric_governance_metadata,
)


def test_dx_link_requires_a_complete_audited_regimen():
    regimen = RegimenEligibility(
        "r", "m", ("dx",), "adjunct", "documented_symptom", ("s",),
        True, "COMPLETE", "PASSED", "drug",
    )
    incomplete = RegimenEligibility(
        "r2", "m", ("dx",), "adjunct", "documented_symptom", (),
        True, "COMPLETE", "PASSED", "drug",
    )
    assert diagnosis_linked_adjuncts([regimen], "dx") == [regimen]
    assert diagnosis_linked_adjuncts([incomplete], "dx") == []
    assert diagnosis_linked_adjuncts([regimen], "other") == []


def test_resolution_states_include_clinical_contraindication():
    assert ResolutionState.CONTRAINDICATED_CLINICAL.value == "CONTRAINDICATED_CLINICAL"


def test_known_diagnosis_is_not_prescribed_without_audited_regimen():
    prescription = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda", 0.8, AgeInput(years=0, months=0, days=2), "28/09/2026"
    )
    assert "DIAGNÓSTICO\nGASTROENTERITE VIRAL AGUDA" in prescription
    assert "PESO\n0.8 kg" in prescription
    assert "IDADE\n2 dias" in prescription
    assert "REQUIRES_CRITICAL_INPUT" in prescription
    assert "PRESCRIÇÃO\nNÃO LIBERADA" in prescription
    assert "ONDANSETRONA" not in prescription
    assert "DIPIRONA" not in prescription


def test_presentation_registry_has_verified_ondansetron_strength_and_source():
    metadata = pediatric_governance_metadata()
    assert metadata["governance_version"] == "61.0-diagnosis-linked-complete-regimens"
    assert metadata["effective_date"] == "2026-08-24"
    assert metadata["presentation_registry_version"] == 61
    assert metadata["triple_audit_passed"] is False
    ondansetron = next(
        item for item in metadata["presentations"]
        if item["presentation_id"] == "ondansetron-enavo-drops-8mg-ml-5ml-br"
    )
    assert ondansetron["strength"] == {"value": 8, "unit": "mg/mL"}
    assert ondansetron["source_ids"] == ["ENAVO_8MG_ML_COMMERCIAL_CROSSCHECK"]
    assert 2.4 / ondansetron["strength"]["value"] == pytest.approx(0.3)


@pytest.mark.parametrize("diagnosis", [
    "Sem faringite",
    "Sem otite",
    "Asfixia",
    "Intoxicação por paracetamol",
    "Hipoglicemia",
    "Choque séptico",
    "Faringite e otite",
])
def test_negative_substring_ambiguous_and_unknown_diagnoses_are_rejected(diagnosis):
    with pytest.raises(ValueError):
        generate_pediatric_prescription(diagnosis, 10, AgeInput(years=3))


@pytest.mark.parametrize("weight", [0, 0.0001, 90.01, float("inf"), float("nan")])
def test_invalid_weights_are_rejected(weight):
    with pytest.raises(ValueError):
        generate_pediatric_prescription("Faringite aguda", weight, AgeInput(years=3))


def test_newborn_weight_and_zero_age_are_valid_inputs_but_still_default_deny():
    payload = PediatricPrescriptionInput(
        diagnosis="Faringite Aguda Viral",
        weight_kg=0.8,
        age=AgeInput(years=0, months=0, days=0),
    )
    assert "NÃO LIBERADA" in generate_pediatric_prescription(
        payload.diagnosis, payload.weight_kg, payload.age
    )


@pytest.mark.parametrize("age", [
    "abc",
    "-5 anos",
    "500 anos",
    {"years": -1},
    {"years": 19},
    {"years": 18, "months": 1},
    {"years": 1, "months": 12},
    {"years": 1, "days": 31},
])
def test_unstructured_or_out_of_range_ages_are_rejected(age):
    with pytest.raises((ValidationError, ValueError)):
        PediatricPrescriptionInput(diagnosis="Faringite", weight_kg=10, age=age)


@pytest.mark.parametrize("visit_date", [
    "2026-02-30",
    "30/02/2026",
    "01/01/1800",
    (date.today() + timedelta(days=1)).strftime("%d/%m/%Y"),
    "28/09/2026\nALTERADO",
])
def test_impossible_historic_future_and_injected_dates_are_rejected(visit_date):
    with pytest.raises((ValidationError, ValueError)):
        PediatricPrescriptionInput(
            diagnosis="Faringite", weight_kg=10, age=AgeInput(years=3), visit_date=visit_date
        )


def test_diagnosis_newline_and_non_finite_or_extreme_input_rejected():
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput(
            diagnosis="Faringite\nIBUPROFENO", weight_kg=10, age=AgeInput(years=3)
        )
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput(
            diagnosis="Faringite", weight_kg=0.0001, age=AgeInput(years=3)
        )
    with pytest.raises(ValueError):
        generate_pediatric_prescription("Faringite", 10, "3 anos")  # type: ignore[arg-type]
