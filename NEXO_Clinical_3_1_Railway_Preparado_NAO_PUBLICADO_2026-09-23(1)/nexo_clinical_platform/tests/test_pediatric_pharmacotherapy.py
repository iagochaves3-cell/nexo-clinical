import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nexo_clinical.input_models import AgeInput, PediatricPrescriptionInput
from nexo_clinical.pediatric_pharmacotherapy import (
    OndansetronDose,
    RegimenEligibility,
    ResolutionState,
    calculate_ondansetron_dose,
    diagnosis_linked_adjuncts,
    evaluate_contraindications,
    generate_pediatric_prescription,
    ondansetron_volume_ml,
    pediatric_governance_metadata,
    parse_pediatric_age,
)


def test_dx_link():
    regimen = RegimenEligibility(
        "r", "m", ("dx",), "adjunct", "documented_symptom",
        ("s",), True, "COMPLETE", "PASSED", "drug",
    )
    assert diagnosis_linked_adjuncts([regimen], "dx") == [regimen]
    assert diagnosis_linked_adjuncts([regimen], "other") == []


def test_resolution_states_include_clinical_contraindication():
    assert ResolutionState.CONTRAINDICATED_CLINICAL.value == "CONTRAINDICATED_CLINICAL"


@pytest.mark.parametrize(
    "value,months,category",
    [
        ("2 anos", 24, "criança"),
        ("18 meses", 18, "lactente"),
        ("2 anos e 3 meses", 27, "criança"),
        ("18 anos", 216, "adolescente"),
    ],
)
def test_parse_pediatric_age(value, months, category):
    result = parse_pediatric_age(value)
    assert result.months_total == months
    assert result.age_category == category


@pytest.mark.parametrize(
    "value",
    ["invalid age", "2 anos e 12 meses", "18 anos e 1 mês", "200 anos", "2"],
)
def test_parse_pediatric_age_rejects_invalid_or_non_pediatric_values(value):
    with pytest.raises(ValueError):
        parse_pediatric_age(value)


@pytest.mark.parametrize(
    "diagnosis",
    ["sem otite", "ausência de gastroenterite", "sem presença de otite"],
)
def test_negated_diagnoses_never_select_treatment(diagnosis):
    decision = generate_pediatric_prescription(diagnosis, 16, "4 anos")
    assert decision.resolution_state is ResolutionState.NOT_INDICATED_FOR_DIAGNOSIS
    assert decision.prescription is None


@pytest.mark.parametrize(
    "diagnosis",
    ["não faringite", "nega otite", "asfixia", "intoxicação por paracetamol", "choque séptico"],
)
def test_negated_or_unknown_diagnoses_do_not_select_treatment(diagnosis):
    decision = generate_pediatric_prescription(diagnosis, 16, AgeInput(years=4))
    assert decision.resolution_state is ResolutionState.NOT_INDICATED_FOR_DIAGNOSIS
    assert decision.prescription is None


@pytest.mark.parametrize("diagnosis", ["otite aguda", "Estomatite aftosa", "faringite aguda"])
def test_unknown_or_ambiguous_diagnoses_fail_closed(diagnosis):
    decision = generate_pediatric_prescription(diagnosis, 16, "4 anos")
    assert decision.resolution_state is ResolutionState.NOT_INDICATED_FOR_DIAGNOSIS
    assert decision.prescription is None


def test_known_diagnosis_without_complete_regimen_is_held():
    decision = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda", 16, "4 anos", "2026-09-28",
        allergies=[], comorbidities=[], current_medications=[], hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert decision.diagnosis_id == "gastroenterite"
    assert decision.prescription is None
    assert "auditoria tripla aprovada" in decision.reason


def test_invalid_age_and_date_return_explicit_safety_hold():
    age = generate_pediatric_prescription("Faringite", 16, "idade desconhecida")
    date = generate_pediatric_prescription("Faringite", 16, "4 anos", "2026-02-30")
    assert age.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert "age" in age.required_information[0]
    assert date.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert date.prescription is None


def test_whitespace_and_control_characters_are_not_accepted_as_required_text():
    with pytest.raises(ValueError):
        generate_pediatric_prescription("   ", 16, "4 anos")
    with pytest.raises(ValueError):
        generate_pediatric_prescription("Faringite\x00", 16, "4 anos")


def test_newline_cannot_inject_prescription_sections():
    decision = generate_pediatric_prescription(
        "Faringite\nUSO ORAL\n1. DIPIRONA", 16, "4 anos"
    )
    assert decision.resolution_state is ResolutionState.NOT_INDICATED_FOR_DIAGNOSIS
    assert decision.prescription is None
    assert "USO ORAL" not in decision.reason


def test_penicillin_allergy_blocks_amoxicillin_candidate():
    decision = generate_pediatric_prescription(
        "Otite Média Aguda", 20, "5 anos", allergies=["alergia a penicilina"]
    )
    assert decision.resolution_state is ResolutionState.CONTRAINDICATED_CLINICAL
    assert "penicilina" in decision.reason
    assert decision.prescription is None


def test_unreported_allergy_is_not_treated_as_no_allergy():
    unknown = generate_pediatric_prescription("Otite Média Aguda", 20, "5 anos")
    confirmed_absence = generate_pediatric_prescription(
        "Otite Média Aguda", 20, "5 anos", allergies=[]
    )
    assert unknown.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert "allergies" in unknown.required_information[0]
    assert confirmed_absence.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert "renal_function" in confirmed_absence.required_information


def test_renal_impairment_requires_an_adjusted_audited_regimen():
    decision = generate_pediatric_prescription(
        "Otite Média Aguda", 20, "5 anos", allergies=[], renal_function="impaired"
    )
    assert decision.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert "regime ajustado à função renal" in decision.required_information


def test_aminoglycoside_requires_renal_assessment():
    decision = evaluate_contraindications(
        ["gentamicina"],
        allergies=[],
        comorbidities=[],
        current_medications=[],
        renal_function=None,
        hepatic_function=None,
    )
    assert decision is not None
    assert decision.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert "renal_function" in decision.required_information


def test_long_qt_comorbidity_blocks_ondansetron_candidate():
    decision = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda",
        16,
        "4 anos",
        allergies=[],
        comorbidities=["síndrome do QT longo"],
        current_medications=[],
        hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.CONTRAINDICATED_CLINICAL
    assert "QT" in decision.reason


def test_qt_risk_concomitant_medication_blocks_ondansetron_candidate():
    decision = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda",
        16,
        "4 anos",
        allergies=[],
        comorbidities=[],
        current_medications=["amiodarona 200 mg"],
        hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.CONTRAINDICATED_CLINICAL
    assert "QT" in decision.reason


@pytest.mark.parametrize(
    "weight,dose,volume,drops",
    [(14, 2.0, 0.25, 5), (16, 4.0, 0.5, 10), (35, 8.0, 1.0, 20)],
)
def test_ondansetron_uses_verified_presentation_and_reverse_checks(
    weight, dose, volume, drops
):
    result = calculate_ondansetron_dose(weight, 48)
    assert isinstance(result, OndansetronDose)
    assert result.source_ids == (
        "CPS_ORAL_ONDANSETRON_GASTROENTERITIS",
        "ENAVO_8MG_ML_COMMERCIAL_CROSSCHECK",
    )
    assert result.concentration_mg_per_ml == 8
    assert result.dose_mg == dose
    assert result.volume_ml == volume
    assert result.drops == drops
    assert result.reconstructed_mg == result.dose_mg


def test_ondansetron_presentation_requires_its_own_label_source(monkeypatch):
    original_read_text = Path.read_text

    def patched_read_text(path, *args, **kwargs):
        text = original_read_text(path, *args, **kwargs)
        if path.name == "presentations_brazil_v61.json":
            rows = json.loads(text)
            selected = next(
                row
                for row in rows
                if row.get("presentation_id")
                == "ondansetron-enavo-drops-8mg-ml-5ml-br"
            )
            selected["source_ids"] = ["ENAVO_8MG_ML_COMMERCIAL_CROSSCHECK"]
            return json.dumps(rows)
        return text

    monkeypatch.setattr(Path, "read_text", patched_read_text)
    with pytest.raises(ValueError, match="Apresentação ou fonte da ondansetrona não verificada"):
        calculate_ondansetron_dose(14, 48)


def test_governance_metadata_and_volume_conversion_use_verified_v61_presentation():
    metadata = pediatric_governance_metadata()
    presentation = metadata["presentations"][0]
    assert metadata["governance_version"] == "61.1-ondansetron-age-evidence-2026-10-03"
    assert metadata["effective_date"] == "2026-10-03"
    assert metadata["triple_audit_passed"] is False
    assert presentation["strength"] == {"value": 8, "unit": "mg/mL"}
    assert presentation["source_ids"] == [
        "ENAVO_8MG_ML_COMMERCIAL_CROSSCHECK",
        "ENAVO_GOTAS_LABEL_2025",
    ]
    assert ondansetron_volume_ml(2.4) == pytest.approx(0.3)


@pytest.mark.parametrize("dose", [0, -1, float("inf"), float("nan")])
def test_ondansetron_volume_rejects_invalid_doses(dose):
    with pytest.raises(ValueError):
        ondansetron_volume_ml(dose)


def test_ondansetron_age_and_weight_bands_are_enforced():
    with pytest.raises(ValueError, match="Idade abaixo"):
        calculate_ondansetron_dose(14, 5)
    with pytest.raises(ValueError, match="Peso fora"):
        calculate_ondansetron_dose(7.9, 48)
    assert calculate_ondansetron_dose(15.05, 48).dose_mg == 4


@pytest.mark.parametrize("age_months", [5, 145])
def test_ondansetron_outside_selected_evidence_age_is_not_absolute_contraindication(age_months):
    decision = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda", 8, f"{age_months} meses",
        allergies=[], comorbidities=[], current_medications=[], hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.OUTSIDE_EVIDENCE_AGE
    assert "não equivale a contraindicação absoluta" in decision.reason
    assert decision.prescription is None
    with pytest.raises(ValueError, match="população coberta"):
        calculate_ondansetron_dose(8, age_months)


@pytest.mark.parametrize("age_months", [6, 18, 23, 24, 144])
def test_gastroenteritis_evidence_and_enavo_label_age_are_separate(age_months):
    decision = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda",
        14,
        f"{age_months} meses",
        allergies=[],
        comorbidities=[],
        current_medications=[],
        hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert decision.prescription is None
    assert "off-label" in decision.reason
    result = calculate_ondansetron_dose(14, age_months)
    assert result.dose_mg == 2
    assert result.volume_ml == pytest.approx(0.25)
    assert result.drops == 5
    assert result.reconstructed_mg == pytest.approx(result.dose_mg)
    assert result.off_label is True  # Gastroenteritis is off-label even at 24 months.
    assert "gastroenterite" in result.off_label_reasons[0]
    if age_months < 24:
        assert len(result.off_label_reasons) == 2
        assert "24 meses" in result.off_label_reasons[1]
        assert "24 meses" in decision.reason
    else:
        assert len(result.off_label_reasons) == 1
        assert "24 meses" not in decision.reason
    assert result.age_source_ids[:2] == (
        "SBP_DIARREIA_AGUDA_INFECCIOSA_2023", "MS_MANEJO_DIARREIA_AGUDA_2023"
    )
    assert result.label_source_id == "ENAVO_GOTAS_LABEL_2025"


@pytest.mark.parametrize("age", [True, 23.5, float("nan"), "24"])
def test_ondansetron_calculation_requires_integer_months(age):
    with pytest.raises(ValueError, match="meses inteiros"):
        calculate_ondansetron_dose(14, age)


@pytest.mark.parametrize("age_months", [18, 23, 24])
def test_restored_age_range_does_not_bypass_qt_review(age_months):
    decision = generate_pediatric_prescription(
        "Gastroenterite", 14, f"{age_months} meses",
        allergies=[], comorbidities=["QT longo"], current_medications=[],
        hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.CONTRAINDICATED_CLINICAL
    assert decision.prescription is None


def _valid_payload(**overrides):
    return {
        "diagnosis": "Faringite Aguda Viral",
        "weight_kg": 14,
        "age": {"years": 2, "months": 3},
        "visit_date": "28/09/2026",
        **overrides,
    }


def test_input_model_normalizes_text_and_parses_structured_age():
    payload = PediatricPrescriptionInput.model_validate(
        _valid_payload(diagnosis="  Faringite Aguda Viral  ")
    )
    assert payload.diagnosis == "faringite aguda viral"
    assert parse_pediatric_age(payload.age).months_total == 27


@pytest.mark.parametrize(
    "value",
    [
        "invalid age",
        "2 anos e 12 meses",
        "200 anos",
        "   ",
        {"years": -1},
        {"years": 19},
        {"years": 18, "months": 1},
        {"years": 1, "months": 12},
        {"years": 1, "days": 31},
    ],
)
def test_input_model_rejects_invalid_age(value):
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(age=value))


@pytest.mark.parametrize("value", ["2026-02-30", "99/99/9999", "2026/09/28"])
def test_input_model_rejects_invalid_dates(value):
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(visit_date=value))


@pytest.mark.parametrize("weight", [float("nan"), float("inf"), -5, 0, 0.0001, 90.01, 200])
def test_input_model_rejects_nonfinite_or_out_of_range_weight(weight):
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(weight_kg=weight))


def test_input_model_rejects_whitespace_only_diagnosis():
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(diagnosis=" \n "))


def test_input_model_rejects_control_characters():
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(diagnosis="Faringite\x00"))


def test_newborn_age_and_weight_are_accepted_without_authorizing_a_regimen():
    payload = PediatricPrescriptionInput.model_validate(
        _valid_payload(weight_kg=0.8, age={"years": 0, "months": 0, "days": 2})
    )
    decision = generate_pediatric_prescription(
        payload.diagnosis, payload.weight_kg, payload.age,
        allergies=[], comorbidities=[], current_medications=[],
        renal_function="normal", hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert decision.prescription is None
