from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import Iterable


class ResolutionState(StrEnum):
    READY = "READY"
    CONTRAINDICATED_AGE = "CONTRAINDICATED_AGE"
    CONTRAINDICATED_WEIGHT = "CONTRAINDICATED_WEIGHT"
    CONTRAINDICATED_CLINICAL = "CONTRAINDICATED_CLINICAL"
    NOT_INDICATED_FOR_DIAGNOSIS = "NOT_INDICATED_FOR_DIAGNOSIS"
    SPECIALIST_ONLY = "SPECIALIST_ONLY"
    REQUIRES_CRITICAL_INPUT = "REQUIRES_CRITICAL_INPUT"
    REGULATORY_SUSPENDED = "REGULATORY_SUSPENDED"


@dataclass(frozen=True)
class RegimenEligibility:
    regimen_id: str
    medication_id: str
    diagnosis_ids: tuple[str, ...]
    role: str
    clinical_target: str
    source_ids: tuple[str, ...]
    presentation_verified_brazil: bool
    completeness_status: str
    triple_audit_status: str
    calculation_component: str
    active: bool = True

    def executable(self) -> bool:
        return bool(
            self.active
            and self.source_ids
            and self.presentation_verified_brazil
            and self.completeness_status == "COMPLETE"
            and self.triple_audit_status == "PASSED"
            and self.calculation_component.strip()
        )


def diagnosis_linked_candidates(
    regimens: Iterable[RegimenEligibility], diagnosis_id: str, role: str | None = None
) -> list[RegimenEligibility]:
    return [
        regimen
        for regimen in regimens
        if regimen.active
        and diagnosis_id in regimen.diagnosis_ids
        and (role is None or regimen.role == role)
        and regimen.executable()
    ]


def diagnosis_linked_adjuncts(
    regimens: Iterable[RegimenEligibility], diagnosis_id: str
) -> list[RegimenEligibility]:
    return diagnosis_linked_candidates(regimens, diagnosis_id, "adjunct")


@dataclass(frozen=True)
class PediatricAge:
    months_total: int
    age_category: str


@dataclass(frozen=True)
class PrescriptionDecision:
    resolution_state: ResolutionState
    reason: str
    required_information: tuple[str, ...] = ()
    diagnosis_id: str | None = None
    age: PediatricAge | None = None
    prescription: str | None = None


@dataclass(frozen=True)
class OndansetronDose:
    dose_mg: float
    volume_ml: float
    drops: int
    concentration_mg_per_ml: float
    reconstructed_mg: float
    source_ids: tuple[str, ...]


MAX_PEDIATRIC_AGE_MONTHS = 18 * 12
ONDANSETRON_MIN_AGE_MONTHS = 6
ONDANSETRON_MAX_AGE_MONTHS = 12 * 12
ONDANSETRON_PRESENTATION_ID = "ondansetron-enavo-drops-8mg-ml-5ml-br"
ONDANSETRON_SOURCE_ID = "CPS_ORAL_ONDANSETRON_GASTROENTERITIS"
PRESENTATION_SOURCE_ID = "ENAVO_8MG_ML_COMMERCIAL_CROSSCHECK"

_YEAR_AGE = re.compile(
    r"(?P<years>\d+)\s*anos?(?:\s+e\s+(?P<months>\d+)\s*m[eê]s(?:es)?)?"
)
_MONTH_AGE = re.compile(r"(?P<months>\d+)\s*m[eê]s(?:es)?")
_NEGATION = re.compile(
    r"\b(?:sem(?:\s+presenca\s+de)?|ausencia\s+de|nao\s+(?:tem|apresenta|evidencia))\b"
)
_DIAGNOSIS_ALIASES = {
    "faringite": "faringite",
    "faringite aguda viral": "faringite",
    "gastroenterite": "gastroenterite",
    "gastroenterite viral aguda": "gastroenterite",
    "otite media aguda": "otite_media_aguda",
    "amigdalite bacteriana": "amigdalite_bacteriana",
    "sinusite bacteriana": "sinusite_bacteriana",
}
_AMBIGUOUS_DIAGNOSES = {
    "amigdalite",
    "amigdalite aguda",
    "faringite aguda",
    "otite",
    "sinusite",
    "sinusite aguda",
}
_DIAGNOSIS_CANDIDATE_MEDICATIONS = {
    "gastroenterite": ("ondansetron",),
    "otite_media_aguda": ("amoxicillin",),
    "amigdalite_bacteriana": ("amoxicillin",),
    "sinusite_bacteriana": ("amoxicillin",),
}
_MEDICATION_ALLERGENS = {
    "amoxicillin": ("amoxicillin", "amoxicilina", "penicillin", "penicilina"),
    "ondansetron": ("ondansetron", "ondansetrona"),
}
_RENAL_ASSESSMENT_MEDICATIONS = {
    "amoxicillin",
    "aminoglycoside",
    "gentamicin",
    "amikacin",
    "tobramycin",
}
_ONDANSETRON_QT_RISK_MEDICATIONS = {
    "amiodarone",
    "amiodarona",
    "sotalol",
    "quinidine",
    "quinidina",
    "clarithromycin",
    "claritromicina",
    "azithromycin",
    "azitromicina",
    "citalopram",
    "escitalopram",
    "domperidone",
    "domperidona",
}
_MEDICATION_ALIASES = {
    "amoxicilina": "amoxicillin",
    "ondansetrona": "ondansetron",
    "gentamicina": "gentamicin",
    "amicacina": "amikacin",
    "tobramicina": "tobramycin",
}


def _clean_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("O campo deve ser texto.")
    cleaned = " ".join(value.split())
    if any(unicodedata.category(char) == "Cc" for char in cleaned):
        raise ValueError("O campo contém caracteres de controle inválidos.")
    return cleaned


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def parse_pediatric_age(value: str) -> PediatricAge:
    age_text = _fold(_clean_text(value))
    match = _YEAR_AGE.fullmatch(age_text)
    if match:
        years = int(match.group("years"))
        months = int(match.group("months") or 0)
        if months >= 12:
            raise ValueError("Os meses adicionais devem estar entre 0 e 11.")
        total_months = years * 12 + months
    else:
        match = _MONTH_AGE.fullmatch(age_text)
        if not match:
            raise ValueError("Idade deve usar anos e/ou meses.")
        total_months = int(match.group("months"))

    if total_months > MAX_PEDIATRIC_AGE_MONTHS:
        raise ValueError("Idade fora do escopo pediátrico (0 a 18 anos).")
    if total_months < 24:
        category = "lactente"
    elif total_months < 144:
        category = "criança"
    else:
        category = "adolescente"
    return PediatricAge(months_total=total_months, age_category=category)


def _parse_visit_date(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _clean_text(value)
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
            parsed = date.fromisoformat(cleaned)
        elif re.fullmatch(r"\d{2}/\d{2}/\d{4}", cleaned):
            parsed = datetime.strptime(cleaned, "%d/%m/%Y").date()
        else:
            raise ValueError
    except ValueError:
        return None
    return parsed.strftime("%d/%m/%Y")


def _load_ondansetron_presentation() -> dict[str, object]:
    data_dir = Path(__file__).with_name("data")
    try:
        presentations = json.loads(
            (data_dir / "presentations_brazil_v61.json").read_text()
        )
        addendum = json.loads(
            (data_dir / "source-registry-addendum-v61.json").read_text()
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Registro da apresentação ou da fonte indisponível.") from exc
    presentation = next(
        (
            row
            for row in presentations
            if row.get("presentation_id") == ONDANSETRON_PRESENTATION_ID
        ),
        None,
    )
    source_ids = {row.get("source_id") for row in addendum.get("sources", [])}
    if (
        presentation is None
        or presentation.get("brazil_status") != "COMMERCIAL_PRESENCE_CROSSCHECKED"
        or PRESENTATION_SOURCE_ID not in presentation.get("source_ids", [])
        or PRESENTATION_SOURCE_ID not in source_ids
        or ONDANSETRON_SOURCE_ID not in source_ids
    ):
        raise ValueError("Apresentação ou fonte da ondansetrona não verificada.")
    strength = presentation.get("strength")
    if not isinstance(strength, dict) or strength.get("unit") != "mg/mL":
        raise ValueError("Concentração da apresentação não verificada.")
    concentration = strength.get("value")
    drops_per_ml = presentation.get("drops_per_mL")
    active_mg_per_drop = presentation.get("active_mg_per_drop")
    if (
        not isinstance(concentration, (int, float))
        or not math.isfinite(concentration)
        or concentration <= 0
        or not isinstance(drops_per_ml, int)
        or drops_per_ml <= 0
        or not isinstance(active_mg_per_drop, (int, float))
        or not math.isclose(
            concentration / drops_per_ml, active_mg_per_drop, rel_tol=0, abs_tol=1e-9
        )
    ):
        raise ValueError("Concentração e fator de gotas inconsistentes.")
    return presentation


def calculate_ondansetron_dose(weight_kg: float, age_months: int) -> OndansetronDose:
    """Calculate the CPS single-dose bands using only the cross-checked Enavo drops."""
    _validate_weight(weight_kg)
    if age_months < ONDANSETRON_MIN_AGE_MONTHS:
        raise ValueError("Idade abaixo da população coberta pela referência selecionada.")
    if age_months > ONDANSETRON_MAX_AGE_MONTHS:
        raise ValueError("Idade acima da população coberta pela referência selecionada.")

    if 8 <= weight_kg <= 15:
        intended_dose_mg = 2.0
    elif 15 < weight_kg <= 30:
        intended_dose_mg = 4.0
    elif weight_kg > 30:
        intended_dose_mg = 8.0
    else:
        raise ValueError("Peso fora das faixas de dose da referência selecionada.")

    presentation = _load_ondansetron_presentation()
    strength = presentation["strength"]
    concentration = float(strength["value"])
    drops_per_ml = int(presentation["drops_per_mL"])
    active_mg_per_drop = float(presentation["active_mg_per_drop"])
    volume_ml = round(intended_dose_mg / concentration, 2)
    drops = round(volume_ml * drops_per_ml)
    reconstructed_mg = drops * active_mg_per_drop
    if not math.isclose(reconstructed_mg, intended_dose_mg, rel_tol=0, abs_tol=1e-9):
        raise ValueError("Falha na conferência reversa mg↔mL↔gotas.")
    return OndansetronDose(
        dose_mg=intended_dose_mg,
        volume_ml=volume_ml,
        drops=drops,
        concentration_mg_per_ml=concentration,
        reconstructed_mg=reconstructed_mg,
        source_ids=(ONDANSETRON_SOURCE_ID, PRESENTATION_SOURCE_ID),
    )


def _allergy_conflict(medication_id: str, allergies: list[str]) -> str | None:
    normalized_allergies = [_fold(_clean_text(item)) for item in allergies]
    for allergen in _MEDICATION_ALLERGENS.get(medication_id, ()):
        normalized_allergen = _fold(allergen)
        if any(
            normalized_allergen == allergy
            or f" {normalized_allergen} " in f" {allergy} "
            for allergy in normalized_allergies
        ):
            return allergen
    return None


def evaluate_contraindications(
    medication_ids: Iterable[str],
    *,
    allergies: list[str] | None,
    comorbidities: list[str] | None,
    current_medications: list[str] | None,
    renal_function: str | None,
    hepatic_function: str | None,
) -> PrescriptionDecision | None:
    """Check allergy, renal, QT/comorbidity, hepatic, and medication-history requirements.

    Amoxicillin and aminoglycosides require renal review. Ondansetron requires
    allergy, QT/comorbidity, concomitant-medication, and hepatic review.
    """
    missing: set[str] = set()
    for medication_id in medication_ids:
        medication_id = _fold(_clean_text(medication_id))
        medication_id = _MEDICATION_ALIASES.get(medication_id, medication_id)
        if allergies is None:
            missing.add("allergies (incluindo confirmação de ausência)")
        else:
            allergen = _allergy_conflict(medication_id, allergies)
            if allergen:
                return PrescriptionDecision(
                    ResolutionState.CONTRAINDICATED_CLINICAL,
                    f"alergia registrada compatível com {medication_id}: {allergen}",
                )

        if medication_id in _RENAL_ASSESSMENT_MEDICATIONS:
            if renal_function in (None, "unknown"):
                missing.add("renal_function")
            elif renal_function == "impaired":
                missing.add("regime ajustado à função renal")

        if medication_id == "ondansetron":
            if comorbidities is None:
                missing.add("comorbidities (incluindo confirmação de ausência)")
            elif any(
                marker in _fold(_clean_text(item))
                for item in comorbidities
                for marker in ("long qt", "qt longo", "prolongamento do qt")
            ):
                return PrescriptionDecision(
                    ResolutionState.CONTRAINDICATED_CLINICAL,
                    "comorbidade compatível com risco de prolongamento do intervalo QT",
                )
            if current_medications is None:
                missing.add("current_medications")
            elif any(
                f" {risk_medication} " in f" {_fold(_clean_text(item))} "
                for item in current_medications
                for risk_medication in _ONDANSETRON_QT_RISK_MEDICATIONS
            ):
                return PrescriptionDecision(
                    ResolutionState.CONTRAINDICATED_CLINICAL,
                    "medicamento em uso com risco de prolongamento do intervalo QT",
                )
            if hepatic_function in (None, "unknown"):
                missing.add("hepatic_function")
            elif hepatic_function == "impaired":
                missing.add("regime avaliado para função hepática")

    if missing:
        return PrescriptionDecision(
            ResolutionState.REQUIRES_CRITICAL_INPUT,
            "avaliação de contraindicações incompleta; ausência de informação não equivale a ausência de risco",
            tuple(sorted(missing)),
        )
    return None


def _validate_weight(weight_kg: float) -> float:
    if (
        isinstance(weight_kg, bool)
        or not isinstance(weight_kg, (int, float))
        or not math.isfinite(weight_kg)
        or weight_kg <= 0
        or weight_kg >= 200
    ):
        raise ValueError("weight_kg deve ser finito, maior que zero e menor que 200.")
    return float(weight_kg)


def _diagnosis_state(diagnosis: str) -> tuple[str | None, str | None]:
    normalized = _fold(diagnosis)
    if _NEGATION.search(normalized):
        return None, "diagnóstico negado"
    diagnosis_id = _DIAGNOSIS_ALIASES.get(normalized)
    if diagnosis_id:
        return diagnosis_id, None
    if normalized in _AMBIGUOUS_DIAGNOSES:
        return None, "diagnóstico ambíguo; especifique o diagnóstico"
    return None, "diagnóstico desconhecido ou sem vínculo explícito"


def generate_pediatric_prescription(
    diagnosis: str,
    weight_kg: float,
    age: str,
    visit_date: str | None = None,
    *,
    allergies: list[str] | None = None,
    comorbidities: list[str] | None = None,
    current_medications: list[str] | None = None,
    renal_function: str | None = None,
    hepatic_function: str | None = None,
) -> PrescriptionDecision:
    diagnosis = _clean_text(diagnosis)
    age_text = _clean_text(age)
    if not diagnosis:
        raise ValueError("diagnosis é obrigatório.")
    if not age_text:
        raise ValueError("age é obrigatório.")
    weight = _validate_weight(weight_kg)
    try:
        structured_age = parse_pediatric_age(age_text)
    except ValueError as exc:
        return PrescriptionDecision(
            ResolutionState.REQUIRES_CRITICAL_INPUT,
            str(exc),
            ("age (anos/meses, entre 0 e 18 anos)",),
        )
    if _parse_visit_date(visit_date) is None and visit_date is not None:
        return PrescriptionDecision(
            ResolutionState.REQUIRES_CRITICAL_INPUT,
            "data da consulta inválida",
            ("visit_date no formato YYYY-MM-DD ou DD/MM/YYYY",),
            age=structured_age,
        )

    diagnosis_id, diagnosis_error = _diagnosis_state(diagnosis)
    if diagnosis_error:
        return PrescriptionDecision(
            ResolutionState.NOT_INDICATED_FOR_DIAGNOSIS,
            diagnosis_error,
            ("diagnóstico afirmativo e não ambíguo",),
            age=structured_age,
        )

    candidate_medications = _DIAGNOSIS_CANDIDATE_MEDICATIONS.get(diagnosis_id, ())
    if "ondansetron" in candidate_medications:
        if not ONDANSETRON_MIN_AGE_MONTHS <= structured_age.months_total <= ONDANSETRON_MAX_AGE_MONTHS:
            return PrescriptionDecision(
                ResolutionState.CONTRAINDICATED_AGE,
                "idade fora da população pediátrica coberta pela referência de ondansetrona selecionada",
                diagnosis_id=diagnosis_id,
                age=structured_age,
            )
        try:
            calculate_ondansetron_dose(weight, structured_age.months_total)
        except ValueError as exc:
            return PrescriptionDecision(
                ResolutionState.REQUIRES_CRITICAL_INPUT,
                str(exc),
                ("peso/faixa de dose ou concentração validada",),
                diagnosis_id=diagnosis_id,
                age=structured_age,
            )

    contraindication = evaluate_contraindications(
        candidate_medications,
        allergies=allergies,
        comorbidities=comorbidities,
        current_medications=current_medications,
        renal_function=renal_function,
        hepatic_function=hepatic_function,
    )
    if contraindication:
        return PrescriptionDecision(
            contraindication.resolution_state,
            contraindication.reason,
            contraindication.required_information,
            diagnosis_id,
            structured_age,
        )

    return PrescriptionDecision(
        ResolutionState.REQUIRES_CRITICAL_INPUT,
        "não há regime completo com vínculo diagnóstico explícito e auditoria tripla aprovada; nenhum medicamento foi gerado",
        (
            "regime operacional com fonte para indicação, população, dose, intervalo, duração e monitoramento",
            "apresentação brasileira e auditoria estrutural, farmacêutica/matemática e clínica/regulatória",
        ),
        diagnosis_id=diagnosis_id,
        age=structured_age,
    )
