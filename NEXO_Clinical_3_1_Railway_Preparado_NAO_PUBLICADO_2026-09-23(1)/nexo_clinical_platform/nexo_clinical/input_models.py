"""Structural HTTP contracts; these models do not validate clinical suitability."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


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
