"""Cálculos clínicos determinísticos, sem decisão de dose.

As funções deste módulo executam somente aritmética e conversão de unidades. Elas não
validam indicação, faixa terapêutica, estabilidade, compatibilidade ou adequação clínica.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .schemas import (
    DoseFromRateResult,
    InfusionResult,
    MaintenanceFluidResult,
    MedicationVolumeResult,
    WeightBasedDoseResult,
)
from .units import (
    canonical_per_hour_to_prescribed,
    convert_quantity,
    dose_to_canonical_per_hour,
    normalize_base_unit,
    parse_dose_unit,
)

_QUANT = Decimal("0.000001")


def _d(value: float | int | str | Decimal | None, field: str, *, allow_zero: bool = False) -> Decimal:
    if value is None:
        raise ValueError(f"{field} é obrigatório.")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} inválido: {value!r}.") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} deve ser finito.")
    if parsed < 0 or (parsed == 0 and not allow_zero):
        comparator = "maior ou igual a zero" if allow_zero else "maior que zero"
        raise ValueError(f"{field} deve ser {comparator}.")
    return parsed


def _optional_d(value: float | int | str | Decimal | None, field: str) -> Decimal | None:
    if value is None:
        return None
    return _d(value, field)


def _round(value: Decimal, places: Decimal = _QUANT) -> float:
    return float(value.quantize(places, rounding=ROUND_HALF_UP))


def _warnings_base(high_alert: bool) -> list[str]:
    warnings = [
        "Resultado aritmético: não confirma indicação, dose clínica, estabilidade ou compatibilidade.",
    ]
    if high_alert:
        warnings.append(
            "Medicamento sinalizado como alta vigilância: realizar dupla checagem "
            "independente de dose, unidade, concentração e bomba."
        )
    return warnings


def calculate_infusion_rate(
    *,
    weight_kg: float | None,
    dose_value: float,
    dose_unit: str,
    drug_amount: float,
    drug_amount_unit: str,
    final_volume_ml: float,
    high_alert: bool = False,
) -> dict[str, Any]:
    """Converte dose de infusão em mL/h com checagem reversa independente."""
    dose = _d(dose_value, "dose_value", allow_zero=True)
    amount = _d(drug_amount, "drug_amount")
    volume = _d(final_volume_ml, "final_volume_ml")
    parsed = parse_dose_unit(dose_unit, require_time=True)
    weight = _optional_d(weight_kg, "weight_kg")
    if parsed.per_kg and weight is None:
        raise ValueError("weight_kg é obrigatório para dose expressa por kg.")

    amount_unit, amount_family = normalize_base_unit(drug_amount_unit)
    if amount_family.name != parsed.family.name:
        raise ValueError(f"Dose em {parsed.family.name} é incompatível com solução em {amount_family.name}.")

    amount_canonical = amount * amount_family.factors[amount_unit]
    concentration = amount_canonical / volume
    total_per_hour = dose_to_canonical_per_hour(dose, parsed, weight_kg=weight)
    rate_ml_h = total_per_hour / concentration

    reverse_total_per_hour = rate_ml_h * concentration
    reverse_dose = canonical_per_hour_to_prescribed(reverse_total_per_hour, parsed, weight_kg=weight)
    reverse_delta = abs(reverse_dose - dose)

    warnings = _warnings_base(high_alert)
    if dose == 0:
        warnings.append("Dose zero: velocidade calculada em 0 mL/h; duração da solução é indefinida.")
    if rate_ml_h > Decimal("1000"):
        warnings.append("Velocidade acima de 1000 mL/h: conferir unidade, concentração e contexto clínico.")
    if Decimal("0") < rate_ml_h < Decimal("0.01"):
        warnings.append("Velocidade abaixo de 0,01 mL/h: confirmar resolução e precisão da bomba disponível.")

    bag_duration = None if rate_ml_h == 0 else volume / rate_ml_h
    result = InfusionResult(
        prescribed_dose=_round(dose),
        prescribed_unit=dose_unit,
        normalized_unit=parsed.normalized,
        category=parsed.family.name,
        weight_kg=_round(weight) if weight is not None else None,
        dose_total_per_min=_round(total_per_hour / Decimal("60")),
        dose_total_per_hour=_round(total_per_hour),
        dose_total_per_day=_round(total_per_hour * Decimal("24")),
        canonical_unit=parsed.family.canonical_unit,
        concentration_per_ml=_round(concentration),
        concentration_unit=f"{parsed.family.canonical_unit}/mL",
        rate_ml_h=_round(rate_ml_h),
        rate_ml_min=_round(rate_ml_h / Decimal("60")),
        volume_6h_ml=_round(rate_ml_h * Decimal("6")),
        volume_12h_ml=_round(rate_ml_h * Decimal("12")),
        volume_24h_ml=_round(rate_ml_h * Decimal("24")),
        bag_duration_h=_round(bag_duration) if bag_duration is not None else None,
        reverse_check_dose=_round(reverse_dose),
        reverse_check_delta=_round(reverse_delta),
        formula=(
            "mL/h = [dose convertida para unidade canônica/h × peso (se /kg)] "
            "÷ [quantidade canônica da droga ÷ volume final]"
        ),
        warnings=warnings,
    )
    return result.to_dict()


def calculate_dose_from_rate(
    *,
    rate_ml_h: float,
    weight_kg: float | None,
    target_dose_unit: str,
    drug_amount: float,
    drug_amount_unit: str,
    final_volume_ml: float,
    high_alert: bool = False,
) -> dict[str, Any]:
    """Calcula a dose correspondente a uma velocidade já programada em mL/h."""
    rate = _d(rate_ml_h, "rate_ml_h", allow_zero=True)
    amount = _d(drug_amount, "drug_amount")
    volume = _d(final_volume_ml, "final_volume_ml")
    parsed = parse_dose_unit(target_dose_unit, require_time=True)
    weight = _optional_d(weight_kg, "weight_kg")
    if parsed.per_kg and weight is None:
        raise ValueError("weight_kg é obrigatório para dose expressa por kg.")

    amount_unit, amount_family = normalize_base_unit(drug_amount_unit)
    if amount_family.name != parsed.family.name:
        raise ValueError("A unidade da solução é incompatível com a unidade de dose solicitada.")
    concentration = amount * amount_family.factors[amount_unit] / volume
    total_per_hour = rate * concentration
    prescribed = canonical_per_hour_to_prescribed(total_per_hour, parsed, weight_kg=weight)

    result = DoseFromRateResult(
        rate_ml_h=_round(rate),
        concentration_per_ml=_round(concentration),
        concentration_unit=f"{parsed.family.canonical_unit}/mL",
        dose_total_per_hour=_round(total_per_hour),
        prescribed_dose=_round(prescribed),
        prescribed_unit=target_dose_unit,
        normalized_unit=parsed.normalized,
        formula=(
            "dose prescrita = [mL/h × concentração canônica/mL] ÷ fator temporal ÷ peso (se /kg) ÷ fator da unidade"
        ),
        warnings=_warnings_base(high_alert),
    )
    return result.to_dict()


def calculate_medication_volume(
    *,
    requested_dose: float,
    requested_dose_unit: str,
    presentation_amount: float,
    presentation_amount_unit: str,
    presentation_volume_ml: float,
    high_alert: bool = False,
) -> dict[str, Any]:
    """Calcula o volume a aspirar de uma apresentação medicamentosa."""
    dose = _d(requested_dose, "requested_dose", allow_zero=True)
    amount = _d(presentation_amount, "presentation_amount")
    volume = _d(presentation_volume_ml, "presentation_volume_ml")

    request_unit, request_family = normalize_base_unit(requested_dose_unit)
    presentation_unit, presentation_family = normalize_base_unit(presentation_amount_unit)
    if request_family.name != presentation_family.name:
        raise ValueError("Dose solicitada e apresentação usam categorias incompatíveis.")

    requested_canonical = dose * request_family.factors[request_unit]
    presentation_canonical = amount * presentation_family.factors[presentation_unit]
    concentration = presentation_canonical / volume
    calculated_volume = requested_canonical / concentration
    units_equivalent = calculated_volume / volume

    warnings = _warnings_base(high_alert)
    if Decimal("0") < calculated_volume < Decimal("0.01"):
        warnings.append("Volume abaixo de 0,01 mL: requer estratégia de diluição e dispositivo com precisão adequada.")
    if calculated_volume > volume:
        warnings.append("O volume calculado excede uma unidade da apresentação; conferir quantidade total disponível.")

    result = MedicationVolumeResult(
        requested_dose=_round(dose),
        requested_unit=requested_dose_unit,
        normalized_requested_unit=request_unit,
        concentration_per_ml=_round(concentration),
        concentration_unit=f"{request_family.canonical_unit}/mL",
        volume_ml=_round(calculated_volume),
        presentation_units_equivalent=_round(units_equivalent),
        formula=(
            f"volume = dose solicitada em {request_family.canonical_unit} ÷ "
            f"concentração em {request_family.canonical_unit}/mL"
        ),
        warnings=warnings,
    )
    return result.to_dict()


def calculate_weight_based_dose(
    *,
    weight_kg: float,
    dose_per_kg: float,
    dose_unit: str,
    max_total_dose: float | None = None,
    max_total_dose_unit: str | None = None,
    presentation_amount: float | None = None,
    presentation_amount_unit: str | None = None,
    presentation_volume_ml: float | None = None,
    high_alert: bool = False,
) -> dict[str, Any]:
    """Calcula dose total por peso e, opcionalmente, aplica teto e converte para mL.

    A unidade deve ser do tipo mg/kg, mcg/kg, U/kg, mmol/kg ou mEq/kg.
    """
    weight = _d(weight_kg, "weight_kg")
    dose = _d(dose_per_kg, "dose_per_kg", allow_zero=True)
    parsed = parse_dose_unit(dose_unit, require_time=False)
    if not parsed.per_kg:
        raise ValueError("dose_unit deve conter /kg para cálculo ponderal.")

    calculated_canonical = dose * weight * parsed.factor_to_canonical
    final_canonical = calculated_canonical
    max_applied = False

    if max_total_dose is not None:
        if max_total_dose_unit is None:
            raise ValueError("max_total_dose_unit é obrigatório quando max_total_dose é informado.")
        maximum = _d(max_total_dose, "max_total_dose", allow_zero=True)
        maximum_canonical = convert_quantity(maximum, max_total_dose_unit, parsed.family.canonical_unit)
        if calculated_canonical > maximum_canonical:
            final_canonical = maximum_canonical
            max_applied = True

    total_in_base = final_canonical / parsed.factor_to_canonical
    volume_ml: float | None = None
    warnings = _warnings_base(high_alert)

    presentation_fields = [presentation_amount, presentation_amount_unit, presentation_volume_ml]
    if any(v is not None for v in presentation_fields):
        if not all(v is not None for v in presentation_fields):
            raise ValueError("Informe amount, unit e volume da apresentação em conjunto.")
        assert presentation_amount is not None
        assert presentation_amount_unit is not None
        assert presentation_volume_ml is not None
        med_volume = calculate_medication_volume(
            requested_dose=float(total_in_base),
            requested_dose_unit=parsed.base_unit,
            presentation_amount=float(presentation_amount),
            presentation_amount_unit=presentation_amount_unit,
            presentation_volume_ml=float(presentation_volume_ml),
            high_alert=high_alert,
        )
        volume_ml = med_volume["volume_ml"]
        warnings.extend(w for w in med_volume["warnings"] if w not in warnings)

    result = WeightBasedDoseResult(
        weight_kg=_round(weight),
        dose_per_kg=_round(dose),
        dose_unit=dose_unit,
        calculated_total_dose=_round(calculated_canonical / parsed.factor_to_canonical),
        final_total_dose=_round(total_in_base),
        total_dose_unit=parsed.base_unit,
        max_total_applied=max_applied,
        volume_ml=volume_ml,
        formula="dose total = peso × dose/kg; aplicar teto absoluto quando fornecido",
        warnings=warnings,
    )
    return result.to_dict()


def calculate_maintenance_fluids(*, weight_kg: float) -> dict[str, Any]:
    """Calcula manutenção hídrica pelas regras 4-2-1 e 100-50-20.

    O resultado é matemático e não incorpora estado volêmico, comorbidades ou restrições.
    """
    weight = _d(weight_kg, "weight_kg")

    if weight <= Decimal("10"):
        hourly = Decimal("4") * weight
        daily = Decimal("100") * weight
    elif weight <= Decimal("20"):
        hourly = Decimal("40") + Decimal("2") * (weight - Decimal("10"))
        daily = Decimal("1000") + Decimal("50") * (weight - Decimal("10"))
    else:
        hourly = Decimal("60") + (weight - Decimal("20"))
        daily = Decimal("1500") + Decimal("20") * (weight - Decimal("20"))

    hourly_from_daily = daily / Decimal("24")
    warnings = [
        "Fórmulas de manutenção basal: ajustar ao contexto clínico, perdas, "
        "função renal/cardíaca e metas de sódio/glicose.",
    ]
    if weight > Decimal("100"):
        warnings.append("Peso acima de 100 kg: confirmar se o protocolo institucional limita o cálculo por peso real.")

    result = MaintenanceFluidResult(
        weight_kg=_round(weight),
        hourly_421_ml_h=_round(hourly),
        daily_100_50_20_ml_day=_round(daily),
        hourly_from_daily_ml_h=_round(hourly_from_daily),
        difference_ml_h=_round(abs(hourly - hourly_from_daily)),
        formulas=[
            "4-2-1 mL/kg/h: 4 para os primeiros 10 kg, 2 para os próximos 10 kg, 1 acima de 20 kg",
            "100-50-20 mL/kg/dia: 100 para os primeiros 10 kg, 50 para os próximos 10 kg, 20 acima de 20 kg",
        ],
        warnings=warnings,
    )
    return result.to_dict()
