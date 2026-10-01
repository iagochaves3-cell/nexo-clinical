import pytest
from pydantic import ValidationError

from nexo_clinical.input_models import PediatricPrescriptionInput
from nexo_clinical.pediatric_pharmacotherapy import (
    OndansetronDose,
    RegimenEligibility,
    ResolutionState,
    calculate_ondansetron_dose,
    diagnosis_linked_adjuncts,
    evaluate_contraindications,
    generate_pediatric_prescription,
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


def test_ondansetron_age_and_weight_bands_are_enforced():
    with pytest.raises(ValueError, match="Idade abaixo"):
        calculate_ondansetron_dose(14, 5)
    with pytest.raises(ValueError, match="Peso fora"):
        calculate_ondansetron_dose(7.9, 48)
    with pytest.raises(ValueError, match="faixas de dose"):
        calculate_ondansetron_dose(15.05, 48)


def test_ondansetron_candidate_under_six_months_is_rejected():
    decision = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda", 8, "5 meses",
        allergies=[], comorbidities=[], current_medications=[], hepatic_function="normal",
    )
    assert decision.resolution_state is ResolutionState.CONTRAINDICATED_AGE
    assert decision.prescription is None


def test_under_two_ondansetron_candidate_is_not_auto_prescribed():
    decision = generate_pediatric_prescription(
        "Gastroenterite Viral Aguda",
        14,
        "18 meses",
        allergies=[],
        comorbidities=[],
        current_medications=[],
        hepatic_function="normal",
    )
    assert calculate_ondansetron_dose(14, 18).dose_mg == 2
    assert decision.resolution_state is ResolutionState.REQUIRES_CRITICAL_INPUT
    assert decision.prescription is None


def _valid_payload(**overrides):
    return {
        "diagnosis": "Faringite Aguda Viral",
        "weight_kg": 14,
        "age": "2 anos e 3 meses",
        "visit_date": "28/09/2026",
        **overrides,
    }


def test_input_model_normalizes_text_and_parses_structured_age():
    payload = PediatricPrescriptionInput.model_validate(
        _valid_payload(diagnosis="  Faringite\nAguda Viral  ", age="2 ANOS E 3 MESES")
    )
    assert payload.diagnosis == "faringite aguda viral"
    assert parse_pediatric_age(payload.age).months_total == 27


@pytest.mark.parametrize("value", ["invalid age", "2 anos e 12 meses", "200 anos", "   "])
def test_input_model_rejects_invalid_age(value):
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(age=value))


@pytest.mark.parametrize("value", ["2026-02-30", "99/99/9999", "2026/09/28"])
def test_input_model_rejects_invalid_dates(value):
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(visit_date=value))


@pytest.mark.parametrize("weight", [float("nan"), float("inf"), -5, 0, 200])
def test_input_model_rejects_nonfinite_or_out_of_range_weight(weight):
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(weight_kg=weight))


def test_input_model_rejects_whitespace_only_diagnosis():
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(diagnosis=" \n "))


def test_input_model_rejects_control_characters():
    with pytest.raises(ValidationError):
        PediatricPrescriptionInput.model_validate(_valid_payload(diagnosis="Faringite\x00"))
