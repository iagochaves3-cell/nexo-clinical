from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl

class EvidenceTier(str, Enum):
    guideline = "guideline"
    systematic_review = "systematic_review"
    randomized_trial = "randomized_trial"
    external_validation = "external_validation"
    observational = "observational"
    consensus = "consensus"
    regulatory = "regulatory"
    narrative = "narrative"
    expert_opinion = "expert_opinion"

class SourceRecord(BaseModel):
    source_id: str
    organization: str
    title: str
    source_type: str
    jurisdiction: str = "global"
    publication_date: str | None = None
    last_verified: str
    canonical_url: str
    status: str = "active"
    scope: list[str] = Field(default_factory=list)
    evidence_role: str
    update_policy: str
    checksum_sha256: str | None = None
    version: str | None = None
    supersedes: str | None = None

class Recommendation(BaseModel):
    recommendation_id: str
    title: str
    domain: str
    population: dict[str, Any] = Field(default_factory=dict)
    trigger: dict[str, Any] = Field(default_factory=dict)
    recommendation: str
    strength: str | None = None
    certainty: str | None = None
    source_ids: list[str]
    version: str
    effective_date: date
    last_reviewed: date
    status: str = "validated"
    contraindications: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    logic: dict[str, Any] = Field(default_factory=dict)
    monitoring: list[str] = Field(default_factory=list)
    reassessment: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)

class DrugRecord(BaseModel):
    drug_id: str
    generic_name: str
    aliases: list[str] = Field(default_factory=list)
    presentations: list[dict[str, Any]] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    indications: list[dict[str, Any]] = Field(default_factory=list)
    contraindications: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)
    incompatibilities: list[str] = Field(default_factory=list)
    stability: list[dict[str, Any]] = Field(default_factory=list)
    renal_adjustment: list[dict[str, Any]] = Field(default_factory=list)
    hepatic_adjustment: list[dict[str, Any]] = Field(default_factory=list)
    monitoring: list[str] = Field(default_factory=list)
    source_ids: list[str]
    version: str
    last_verified: date
    status: str = "validated"

class ClinicalQuery(BaseModel):
    text: str
    domain_hint: str | None = None
    patient_context: dict[str, Any] = Field(default_factory=dict)
    attachments: list[str] = Field(default_factory=list)
    locale: str = "pt-BR"

class EvidenceCitation(BaseModel):
    source_id: str
    title: str
    organization: str
    url: str
    last_verified: str
    version: str | None = None

class ClinicalAnswer(BaseModel):
    answer: str
    domain: str
    specialists: list[str]
    citations: list[EvidenceCitation]
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    safety_findings: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    protocol_versions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
