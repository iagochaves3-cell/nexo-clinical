"""Structural HTTP contracts; these models do not validate clinical suitability."""
from __future__ import annotations

from datetime import date, datetime
import re
import unicodedata
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
    def validate_pediatric_age(self) -> AgeInput:
        if self.years == 18 and (self.months or self.days):
            raise ValueError("A idade não pode exceder 18 anos.")
        return self

    @property
    def months_total(self) -> int:
        return self.years * 12 + self.months

    @property
    def age_category(self) -> str:
        if self.months_total < 24:
            return "lactente"
        if self.months_total < 144:
            return "criança"
        return "adolescente"

    def display(self) -> str:
        parts = []
        if self.years:
            parts.append(f"{self.years} {'ano' if self.years == 1 else 'anos'}")
        if self.months:
            parts.append(f"{self.months} {'mês' if self.months == 1 else 'meses'}")
        if self.days:
            parts.append(f"{self.days} {'dia' if self.days == 1 else 'dias'}")
        return " e ".join(parts) if parts else "recém-nascido"


class PediatricPrescriptionInput(StrictInput):
    diagnosis: str = Field(min_length=1, max_length=200)
    weight_kg: float = Field(ge=0.1, le=90, allow_inf_nan=False)
    age: AgeInput
    visit_date: str | None = Field(default=None, min_length=1, max_length=20)
    allergies: list[str] | None = None
    comorbidities: list[str] | None = None
    current_medications: list[str] | None = None
    renal_function: Literal["normal", "impaired", "unknown"] | None = None
    hepatic_function: Literal["normal", "impaired", "unknown"] | None = None

    @field_validator("diagnosis", "age", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if any(
            unicodedata.category(char) == "Cc" and not char.isspace()
            for char in value
        ):
            raise ValueError("O campo contém caracteres de controle inválidos.")
        return " ".join(value.split()).casefold()

    @field_validator("allergies", "comorbidities", "current_medications", mode="before")
    @classmethod
    def normalize_history_items(cls, value: Any) -> Any:
        if value is None or not isinstance(value, list):
            return value
        normalized = []
        for item in value:
            if isinstance(item, str):
                if any(
                    unicodedata.category(char) == "Cc" and not char.isspace()
                    for char in item
                ):
                    raise ValueError("Itens clínicos contêm caracteres de controle inválidos.")
                item = " ".join(item.split())
                if not item:
                    raise ValueError("Itens clínicos não podem estar vazios.")
            normalized.append(item)
        return normalized

    @field_validator("visit_date")
    @classmethod
    def validate_visit_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed = date.fromisoformat(value)
        elif re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
            parsed = datetime.strptime(value, "%d/%m/%Y").date()
        else:
            raise ValueError("Use YYYY-MM-DD ou DD/MM/YYYY.")
        if parsed < date(1900, 1, 1) or parsed > date.today():
            raise ValueError("A data deve estar entre 01/01/1900 e hoje.")
        return value
