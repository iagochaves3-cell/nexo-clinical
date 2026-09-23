"""Modelos de dados compartilhados pelo Nexo AI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class InfusionResult:
    prescribed_dose: float
    prescribed_unit: str
    normalized_unit: str
    category: str
    weight_kg: float | None
    dose_total_per_min: float
    dose_total_per_hour: float
    dose_total_per_day: float
    canonical_unit: str
    concentration_per_ml: float
    concentration_unit: str
    rate_ml_h: float
    rate_ml_min: float
    volume_6h_ml: float
    volume_12h_ml: float
    volume_24h_ml: float
    bag_duration_h: float | None
    reverse_check_dose: float
    reverse_check_delta: float
    formula: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DoseFromRateResult:
    rate_ml_h: float
    concentration_per_ml: float
    concentration_unit: str
    dose_total_per_hour: float
    prescribed_dose: float
    prescribed_unit: str
    normalized_unit: str
    formula: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MedicationVolumeResult:
    requested_dose: float
    requested_unit: str
    normalized_requested_unit: str
    concentration_per_ml: float
    concentration_unit: str
    volume_ml: float
    presentation_units_equivalent: float
    formula: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WeightBasedDoseResult:
    weight_kg: float
    dose_per_kg: float
    dose_unit: str
    calculated_total_dose: float
    final_total_dose: float
    total_dose_unit: str
    max_total_applied: bool
    volume_ml: float | None
    formula: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MaintenanceFluidResult:
    weight_kg: float
    hourly_421_ml_h: float
    daily_100_50_20_ml_day: float
    hourly_from_daily_ml_h: float
    difference_ml_h: float
    formulas: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
