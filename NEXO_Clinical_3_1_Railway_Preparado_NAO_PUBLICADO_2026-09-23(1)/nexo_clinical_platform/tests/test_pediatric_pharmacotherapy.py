import pytest

from nexo_clinical.pediatric_pharmacotherapy import (
    RegimenEligibility,
    ResolutionState,
    diagnosis_linked_adjuncts,
    generate_pediatric_prescription,
)


def test_dx_link():
    r = RegimenEligibility("r", "m", ("dx",), "adjunct", "documented_symptom", ("s",), True, "COMPLETE", "PASSED", "drug")
    assert diagnosis_linked_adjuncts([r], "dx") == [r]
    assert diagnosis_linked_adjuncts([r], "other") == []


def test_resolution_states_include_clinical_contraindication():
    assert ResolutionState.CONTRAINDICATED_CLINICAL.value == "CONTRAINDICATED_CLINICAL"


def test_generate_prescription_faringitis_path():
    text = generate_pediatric_prescription("Faringite Aguda Viral", 14, "2 anos e 3 meses", "28/09/2026")
    assert "DIAGNÓSTICO\nFARINGITE AGUDA VIRAL" in text
    assert "PESO\n14 kg" in text
    assert "USO ORAL" in text
    assert "USO NASAL" in text
    assert "Dar 8 gotas por via oral a cada 6 horas" in text
    assert "Dar 21 gotas por via oral a cada 8 horas" in text


def test_generate_prescription_gastro_path():
    text = generate_pediatric_prescription("Gastroenterite Viral Aguda", 16, "4 anos", "28/09/2026")
    assert "ONDANSETRONA 0,8 MG/ML SOLUÇÃO ORAL" in text
    assert "Dar 3.0 mL por via oral a cada 8 horas" in text


def test_generate_prescription_bacterial_path():
    text = generate_pediatric_prescription("Otite Média Aguda", 20, "5 anos", "28/09/2026")
    assert "AMOXICILINA 250 MG/5 ML SUSPENSÃO ORAL" in text
    assert "Dar 6.6 mL por via oral a cada 8 horas durante 10 dias" in text
    assert "USO NASAL" in text


def test_generate_prescription_generic_fallback():
    text = generate_pediatric_prescription("Estomatite aftosa", 10, "3 anos", "28/09/2026")
    assert "USO ORAL" in text
    assert "USO NASAL" not in text
    assert "Melhora gradual dos sintomas" in text


def test_generate_prescription_validates_required_fields():
    with pytest.raises(ValueError):
        generate_pediatric_prescription("", 10, "3 anos", "28/09/2026")
    with pytest.raises(ValueError):
        generate_pediatric_prescription("Faringite", 0, "3 anos", "28/09/2026")
    with pytest.raises(ValueError):
        generate_pediatric_prescription("Faringite", 10, "", "28/09/2026")
