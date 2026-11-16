from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,str_strip_whitespace=True)

class SyntheticPair(Strict):
    company_key: str=Field(min_length=1,max_length=80)
    process_key: str=Field(min_length=1,max_length=120)
    profile: dict
    opportunity: dict
    retrieval_origin: Literal['independent_search','legacy_only','v2_only','both','random_frame']='random_frame'

class CampaignIn(Strict):
    name: str=Field(min_length=3,max_length=160)
    scope: Literal['synthetic','authorized_real']='synthetic'
    synthetic_pairs: list[SyntheticPair]=Field(default_factory=list,max_length=500)
    additional_opportunity_ids: list[int]=Field(default_factory=list,max_length=500)
    independent_search_reference: str|None=Field(default=None,max_length=1000)
    grant_ids: list[str]=Field(default_factory=list,max_length=20)
    run_ids: list[str]=Field(default_factory=list,max_length=20)
    authorization_reference: str=Field(min_length=10,max_length=500)
    blinded_sharing_authorized: bool=False
    documentary_excerpts_authorized: bool=False
    external_text_authorized: bool=False
    provider_terms_reference: str|None=Field(default=None,max_length=500)
    sample_size: int=Field(default=100,ge=1,le=200)
    seed: int=20261115
    holdout_fraction: float=Field(default=.2,ge=0,lt=1)
    max_external_calls: int=Field(default=0,ge=0,le=200)
    max_cost_usd: float=Field(default=.25,gt=0,le=10)
    @model_validator(mode='after')
    def permissions(self):
        if not self.blinded_sharing_authorized:raise ValueError('Explicit permission for blind sharing required')
        if self.scope=='authorized_real' and (not (self.run_ids or self.grant_ids) or self.synthetic_pairs):raise ValueError('Real data requires owned frozen runs')
        if self.scope=='synthetic' and (not self.synthetic_pairs or self.run_ids or self.grant_ids):raise ValueError('Synthetic data requires explicit fictitious pairs')
        if self.external_text_authorized and not self.provider_terms_reference:raise ValueError('Provider conditions review reference required')
        if self.additional_opportunity_ids and (self.scope!='authorized_real' or not self.independent_search_reference):raise ValueError('Independent public candidates require authorized profile and search provenance')
        if self.max_external_calls and not self.external_text_authorized:raise ValueError('External transmission not authorized')
        return self

class AssignIn(Strict):
    sample_ids: list[str]=Field(min_length=1,max_length=200)
    evaluator_user_ids: list[int]=Field(min_length=1,max_length=2)
    kind: Literal['REVIEW','ADJUDICATION']='REVIEW'

class JudgmentIn(Strict):
    relevance: int=Field(ge=0,le=3,strict=True)
    eligibility: Literal['NOT_EVALUABLE','PENDING_VERIFICATION','ELIGIBLE_VERIFIED','NOT_ELIGIBLE_VERIFIED']='NOT_EVALUABLE'
    evidence_quality: Literal['INSUFFICIENT','DECLARED','DOCUMENTED','VERIFIED']='INSUFFICIENT'
    reason: str=Field(min_length=10,max_length=2000)
    pending_requirements: list[str]=Field(default_factory=list,max_length=50)
    supporting_reference: str|None=Field(default=None,max_length=1000)
    @model_validator(mode='after')
    def verified_requires_reference(self):
        if (self.eligibility in {'ELIGIBLE_VERIFIED','NOT_ELIGIBLE_VERIFIED'} or self.evidence_quality=='VERIFIED') and not self.supporting_reference:raise ValueError('Human verified opinion requires supporting reference; not a legal certificate')
        return self


class GrantIn(Strict):
    run_id: str
    administrator_user_id: int
    authorization_reference: str=Field(min_length=10,max_length=500)
    blinded_sharing_authorized: bool
    documentary_excerpts_authorized: bool=False
    external_text_authorized: bool=False
    provider_terms_reference: str|None=Field(default=None,max_length=500)
    expires_days: int=Field(default=30,ge=1,le=30)
    @model_validator(mode='after')
    def confirmed(self):
        if not self.blinded_sharing_authorized:raise ValueError('Explicit blind sharing permission required')
        if self.external_text_authorized and not self.provider_terms_reference:raise ValueError('Provider review required')
        return self
