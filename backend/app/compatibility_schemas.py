"""Additive V2 contract. Null index/subscore means unknown, never zero evidence."""
from typing import Any, Literal
from pydantic import BaseModel, Field

class CriterionOut(BaseModel):
    criterion: str
    state: Literal['VERIFIED_MATCH','VERIFIED_MISMATCH','PARTIAL_MATCH','UNKNOWN','NOT_APPLICABLE']
    weight: float=Field(ge=0)
    subscore: float|None=Field(default=None,ge=0,le=1)
    information_fraction: float=Field(ge=0,le=1)
    contribution: float|None=None
    normalized_contribution: float|None=None
    reason: str
    company_value: Any=None
    contract_value: Any=None
    source: Any=None
    evaluated_at: str
    model_version: str

class SensitivityOut(BaseModel):
    lower: float|None=Field(default=None,ge=0,le=100)
    upper: float|None=Field(default=None,ge=0,le=100)

class CompatibilityOut(BaseModel):
    evidence_summary: dict
    compatibility_score: float|None=Field(default=None,ge=0,le=100)
    score_status: Literal['COMPLETE','PROVISIONAL','INSUFFICIENT_INFORMATION','INSUFFICIENT_CONTRACTUAL_AFFINITY']
    eligibility_status: Literal['ELIGIBLE_VERIFIED','NOT_ELIGIBLE_VERIFIED','PENDING_VERIFICATION','NOT_EVALUABLE']
    evidence_coverage: float=Field(ge=0,le=100)
    normalization_weight: float=Field(ge=0)
    sensitivity_interval: SensitivityOut
    observed_affinity: float|None=Field(default=None,ge=0,le=100)
    criteria: list[CriterionOut]
    requirements: list[dict]
    pending_requirements: list[str|None]
    explanations: list[dict]
    warnings: list[str]
    timings_ms: dict[str,float]|None=None
    recommend_participation: bool
    model_version: str
    input_versions: dict[str,str]
    evaluated_at: str

class ShadowComparisonOut(BaseModel):
    opportunity_id: int
    legacy_score: float|None
    legacy_versions: dict
    v2: CompatibilityOut
    difference: float|None
    duration_ms: float

class ShadowRunOut(BaseModel):
    id: str
    state: str
    processed: int
    total: int
    model_version: str
    snapshot_as_of: str
    results: list[ShadowComparisonOut]
