"""Structural HTTP contracts; these models do not validate clinical suitability."""
from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class LaboratoryInput(StrictInput):
    na: float | None = None
    cl: float | None = None
    hco3: float | None = None
    k: float | None = None
    glucose_mg_dl: float | None = None
    bun_mg_dl: float | None = None


class ECGInput(StrictInput):
    format: Literal["digital_signal", "pdf_vector", "image"] | None = None
    lead_count: int | None = Field(default=None, gt=0)
    speed_mm_s: float | None = Field(default=None, gt=0)
    gain_mm_mv: float | None = Field(default=None, gt=0)


class SafetyContext(BaseModel):
    # Preserve additional context while validating fields consumed by the rules.
    model_config = ConfigDict(extra="allow", strict=True, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, gt=0)
    input_quality: str | None = None


class SafetyInput(StrictInput):
    text: str = ""
    context: SafetyContext = Field(default_factory=SafetyContext)
    citations: list[str | dict[str, Any]] = Field(default_factory=list)


class AgeInput(StrictInput):
    years: int = Field(ge=0, le=18)
    months: int = Field(default=0, ge=0, le=11)
    days: int = Field(default=0, ge=0, le=30)

    @model_validator(mode="after")
    def age_is_within_pediatric_range(self):
        if self.years == 18 and (self.months or self.days):
            raise ValueError("A idade não pode exceder 18 anos.")
        return self

    def display(self) -> str:
        parts = []
        if self.years:
            parts.append(f"{self.years} {'ano' if self.years == 1 else 'anos'}")
        if self.months:
            parts.append(f"{self.months} {'mês' if self.months == 1 else 'meses'}")
        if self.days:
            parts.append(f"{self.days} {'dia' if self.days == 1 else 'dias'}")
        return " e ".join(parts) if parts else "recém-nascido"


def parse_visit_date(value: str) -> date:
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise ValueError("visit_date deve ser uma data válida.")
    parsed = None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            pass
    if parsed is None or parsed < date(1900, 1, 1) or parsed > date.today():
        raise ValueError("visit_date deve estar entre 01/01/1900 e hoje.")
    return parsed


class PediatricPrescriptionInput(StrictInput):
    diagnosis: str = Field(min_length=1, max_length=200)
    weight_kg: float = Field(ge=0.1, le=90)
    age: AgeInput
    visit_date: str | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("diagnosis")
    @classmethod
    def diagnosis_is_single_line(cls, value: str) -> str:
        if not value.strip() or any(unicodedata.category(char) == "Cc" for char in value):
            raise ValueError("diagnosis deve ser texto não vazio em uma única linha.")
        return value.strip()

    @field_validator("visit_date")
    @classmethod
    def visit_date_is_valid(cls, value: str | None) -> str | None:
        if value is not None:
            parse_visit_date(value)
        return value
