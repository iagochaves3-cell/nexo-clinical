"""Normalização e conversão determinística de unidades clínicas.

Este módulo não define doses clinicamente apropriadas. Ele apenas converte unidades.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Final


@dataclass(frozen=True)
class UnitFamily:
    name: str
    canonical_unit: str
    factors: dict[str, Decimal]


MASS: Final = UnitFamily(
    name="mass",
    canonical_unit="mcg",
    factors={
        "kg": Decimal("1000000000"),
        "g": Decimal("1000000"),
        "mg": Decimal("1000"),
        "mcg": Decimal("1"),
        "ng": Decimal("0.001"),
    },
)
ACTIVITY: Final = UnitFamily(
    name="activity",
    canonical_unit="U",
    factors={"U": Decimal("1"), "mU": Decimal("0.001")},
)
SUBSTANCE: Final = UnitFamily(
    name="substance",
    canonical_unit="mmol",
    factors={
        "mol": Decimal("1000"),
        "mmol": Decimal("1"),
        "umol": Decimal("0.001"),
    },
)
EQUIVALENT: Final = UnitFamily(
    name="equivalent",
    canonical_unit="mEq",
    factors={"Eq": Decimal("1000"), "mEq": Decimal("1"), "uEq": Decimal("0.001")},
)

FAMILIES: Final = (MASS, ACTIVITY, SUBSTANCE, EQUIVALENT)
TIME_TO_HOUR: Final = {
    "s": Decimal("3600"),
    "min": Decimal("60"),
    "h": Decimal("1"),
    "day": Decimal("0.04166666666666666666666666667"),
}

_BASE_ALIASES: Final = {
    "μg": "mcg",
    "µg": "mcg",
    "ug": "mcg",
    "microgram": "mcg",
    "micrograms": "mcg",
    "micrograma": "mcg",
    "microgramas": "mcg",
    "ui": "U",
    "iu": "U",
    "unit": "U",
    "units": "U",
    "unidade": "U",
    "unidades": "U",
    "mu": "mU",
    "mui": "mU",
    "miu": "mU",
    "μmol": "umol",
    "µmol": "umol",
    "micromol": "umol",
    "μeq": "uEq",
    "µeq": "uEq",
}
_TIME_ALIASES: Final = {
    "sec": "s",
    "second": "s",
    "seconds": "s",
    "seg": "s",
    "segundo": "s",
    "segundos": "s",
    "minute": "min",
    "minutes": "min",
    "minuto": "min",
    "minutos": "min",
    "hr": "h",
    "hour": "h",
    "hours": "h",
    "hora": "h",
    "horas": "h",
    "d": "day",
    "dia": "day",
    "dias": "day",
}
_KG_ALIASES: Final = {"quilo": "kg", "quilos": "kg", "kilogram": "kg", "kilograms": "kg"}


@dataclass(frozen=True)
class ParsedDoseUnit:
    original: str
    normalized: str
    base_unit: str
    family: UnitFamily
    per_kg: bool
    time_unit: str

    @property
    def factor_to_canonical(self) -> Decimal:
        return self.family.factors[self.base_unit]

    @property
    def canonical_dose_unit(self) -> str:
        suffix = "/kg" if self.per_kg else ""
        return f"{self.family.canonical_unit}{suffix}/{self.time_unit}"


def _clean(text: str) -> str:
    value = text.strip().replace("·", "/").replace("⁄", "/")
    value = re.sub(r"\s+", "", value)
    value = value.replace("por", "/")
    return value


def normalize_base_unit(unit: str) -> tuple[str, UnitFamily]:
    raw = _clean(unit)
    alias_key = raw.lower()
    normalized = _BASE_ALIASES.get(alias_key, raw)

    # Preserve clinically meaningful capitalization.
    canonical_candidates = {
        "u": "U",
        "mu": "mU",
        "eq": "Eq",
        "meq": "mEq",
        "ueq": "uEq",
    }
    normalized = canonical_candidates.get(normalized.lower(), normalized)

    for family in FAMILIES:
        if normalized in family.factors:
            return normalized, family
    raise ValueError(f"Unidade de quantidade não suportada: {unit!r}.")


def parse_dose_unit(unit: str, *, require_time: bool = True) -> ParsedDoseUnit:
    """Interpreta unidades como mcg/kg/min, mg/h, U/kg/day ou mmol/kg/h."""
    original = unit
    value = _clean(unit)
    parts = [p for p in value.split("/") if p]
    if not parts:
        raise ValueError("Unidade de dose vazia.")

    base, family = normalize_base_unit(parts[0])
    per_kg = False
    time_unit: str | None = None

    for raw_part in parts[1:]:
        key = raw_part.lower()
        key = _KG_ALIASES.get(key, key)
        key = _TIME_ALIASES.get(key, key)
        if key == "kg":
            if per_kg:
                raise ValueError(f"Unidade inválida com /kg repetido: {unit!r}.")
            per_kg = True
        elif key in TIME_TO_HOUR:
            if time_unit is not None:
                raise ValueError(f"Unidade inválida com dois denominadores de tempo: {unit!r}.")
            time_unit = key
        else:
            raise ValueError(f"Componente de unidade não suportado: {raw_part!r} em {unit!r}.")

    if require_time and time_unit is None:
        raise ValueError(f"A unidade deve incluir tempo (/min, /h ou /day): {unit!r}.")
    if not require_time and time_unit is not None:
        raise ValueError("Dose sem tempo não aceita denominador temporal.")
    if time_unit is None:
        time_unit = "h"  # Convenção interna apenas para dose sem tempo.

    suffix = "/kg" if per_kg else ""
    normalized = f"{base}{suffix}/{time_unit}" if require_time else f"{base}{suffix}"
    return ParsedDoseUnit(
        original=original,
        normalized=normalized,
        base_unit=base,
        family=family,
        per_kg=per_kg,
        time_unit=time_unit,
    )


def convert_quantity(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    source, source_family = normalize_base_unit(from_unit)
    target, target_family = normalize_base_unit(to_unit)
    if source_family.name != target_family.name:
        raise ValueError(
            f"Categorias incompatíveis: {from_unit!r} ({source_family.name}) e {to_unit!r} ({target_family.name})."
        )
    canonical = value * source_family.factors[source]
    return canonical / target_family.factors[target]


def dose_to_canonical_per_hour(
    dose_value: Decimal,
    parsed: ParsedDoseUnit,
    *,
    weight_kg: Decimal | None,
) -> Decimal:
    if parsed.per_kg:
        if weight_kg is None:
            raise ValueError("weight_kg é obrigatório para uma dose por kg.")
        total = dose_value * weight_kg
    else:
        total = dose_value

    canonical_per_time = total * parsed.factor_to_canonical
    return canonical_per_time * TIME_TO_HOUR[parsed.time_unit]


def canonical_per_hour_to_prescribed(
    canonical_per_hour: Decimal,
    parsed: ParsedDoseUnit,
    *,
    weight_kg: Decimal | None,
) -> Decimal:
    value = canonical_per_hour / TIME_TO_HOUR[parsed.time_unit]
    value = value / parsed.factor_to_canonical
    if parsed.per_kg:
        if weight_kg is None:
            raise ValueError("weight_kg é obrigatório para uma dose por kg.")
        value = value / weight_kg
    return value
