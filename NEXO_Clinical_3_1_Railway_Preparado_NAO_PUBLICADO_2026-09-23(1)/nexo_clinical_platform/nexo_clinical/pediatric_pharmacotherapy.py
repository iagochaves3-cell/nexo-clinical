from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import lru_cache
from importlib.resources import files
import json
import math
import re
import unicodedata
from typing import Iterable

from .input_models import AgeInput, parse_visit_date


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
    regimens: Iterable[RegimenEligibility],
    diagnosis_id: str,
    role: str | None = None,
) -> list[RegimenEligibility]:
    return [
        regimen for regimen in regimens
        if regimen.active
        and diagnosis_id in regimen.diagnosis_ids
        and (role is None or regimen.role == role)
        and regimen.executable()
    ]


def diagnosis_linked_adjuncts(
    regimens: Iterable[RegimenEligibility], diagnosis_id: str
) -> list[RegimenEligibility]:
    return diagnosis_linked_candidates(regimens, diagnosis_id, "adjunct")


_DATA = files("nexo_clinical.data")


@lru_cache(maxsize=1)
def pediatric_governance_metadata() -> dict:
    governance_text = _DATA.joinpath("pediatric-pharmacotherapy-governance.yaml").read_text(
        encoding="utf-8"
    )
    presentation_records = json.loads(
        _DATA.joinpath("presentations_brazil_v61.json").read_text(encoding="utf-8")
    )
    source_registry = json.loads(
        _DATA.joinpath("source-registry-addendum-v61.json").read_text(encoding="utf-8")
    )

    version = re.search(r"(?m)^  version: ([^\r\n]+)$", governance_text)
    effective_date = re.search(r"(?m)^  effective_date: ([^\r\n]+)$", governance_text)
    required_governance = (
        "id: pediatric-pharmacotherapy-governance",
        "default: deny",
        "- diagnosis_relation_is_explicit",
        "- patient_population_matches",
        "- complete_operational_regimen",
        "- brazilian_presentation_verified",
        "- regimen_level_source_present",
        "- triple_audit_passed",
        "lexical_matching_allowed: false",
    )
    if (
        not version
        or not effective_date
        or not all(item in governance_text for item in required_governance)
    ):
        raise ValueError("Configuração de governança pediátrica inválida.")

    source_ids = {item.get("source_id") for item in source_registry.get("sources", [])}
    presentations = []
    for item in presentation_records:
        strength = item.get("strength", {})
        item_source_ids = item.get("source_ids", [])
        if (
            item.get("brazil_status") != "COMMERCIAL_PRESENCE_CROSSCHECKED"
            or item.get("last_verified") != effective_date.group(1)
            or not item_source_ids
            or not set(item_source_ids).issubset(source_ids)
            or not isinstance(strength.get("value"), (int, float))
            or strength.get("value", 0) <= 0
            or not strength.get("unit")
        ):
            continue
        presentations.append({
            "presentation_id": item["presentation_id"],
            "generic_name": item["generic_name"],
            "strength": strength,
            "dosage_form": item["dosage_form"],
            "route": item["route"],
            "source_ids": item_source_ids,
            "last_verified": item["last_verified"],
        })

    return {
        "configuration_id": "pediatric-pharmacotherapy-governance",
        "governance_version": version.group(1),
        "effective_date": effective_date.group(1),
        "source_registry_version": source_registry["registry_version"],
        "presentation_registry_version": 61,
        "presentations": presentations,
        "complete_regimen_count": 0,
        "triple_audit_passed": False,
    }


_DIAGNOSIS_PATTERNS = {
    "faringite": re.compile(r"\bfaringite\b"),
    "resfriado": re.compile(r"\bresfriado\b"),
    "ivas": re.compile(r"\bivas\b"),
    "gastroenterite": re.compile(r"\bgastroenterite\b"),
    "otite": re.compile(r"\botite\b"),
    "amigdalite": re.compile(r"\bamigdalite\b"),
    "sinusite": re.compile(r"\bsinusite\b"),
}
_NEGATION = re.compile(r"\b(?:sem|nega|negando|ausencia de|ausente|descarta|descartado)\b")


def _normalize_diagnosis(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("diagnosis é obrigatório.")
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise ValueError("diagnosis deve ser texto em uma única linha.")
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    matched = [key for key, pattern in _DIAGNOSIS_PATTERNS.items() if pattern.search(normalized)]
    if _NEGATION.search(normalized) and matched:
        raise ValueError("Diagnóstico negado não pode selecionar farmacoterapia.")
    if len(matched) != 1:
        raise ValueError("Diagnóstico desconhecido ou ambíguo; farmacoterapia não liberada.")
    return value.strip(), matched[0]


def _validate_weight(weight_kg: float) -> float:
    if (
        isinstance(weight_kg, bool)
        or not isinstance(weight_kg, (int, float))
        or not math.isfinite(weight_kg)
        or weight_kg < 0.1
        or weight_kg > 90
    ):
        raise ValueError("weight_kg deve ser finito e estar entre 0,1 e 90 kg.")
    return float(weight_kg)


def _format_date(value: str | None) -> str:
    if value is None:
        return date.today().strftime("%d/%m/%Y")
    return parse_visit_date(value).strftime("%d/%m/%Y")


def generate_pediatric_prescription(
    diagnosis: str,
    weight_kg: float,
    age: AgeInput,
    visit_date: str | None = None,
) -> str:
    diagnosis, _ = _normalize_diagnosis(diagnosis)
    weight = _validate_weight(weight_kg)
    if not isinstance(age, AgeInput):
        raise ValueError("age deve conter anos, meses e dias estruturados.")
    visit = _format_date(visit_date)
    metadata = pediatric_governance_metadata()

    output = [
        f"DIAGNÓSTICO\n{diagnosis.upper()}",
        f"PESO\n{weight:g} kg",
        f"IDADE\n{age.display()}",
        f"DATA\n{visit}",
        f"ESTADO DE RESOLUÇÃO\n{ResolutionState.REQUIRES_CRITICAL_INPUT.value}",
        "PRESCRIÇÃO\nNÃO LIBERADA: não há esquema pediátrico completo, vinculado ao diagnóstico e aprovado em auditoria tripla no registry.",
        f"GOVERNANÇA\n{metadata['configuration_id']} v{metadata['governance_version']} (efetiva em {metadata['effective_date']})",
        "REVISÃO HUMANA OBRIGATÓRIA\nSIM",
        "AUTORIZAÇÃO DE PRESCRIÇÃO\nNÃO",
    ]
    return "\n\n".join(output)
