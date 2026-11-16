"""Private experimental index. No probability, legal certification, or legacy writes.

For applicable mass T, observed mass K and supported weighted sum A:
L=100 A/T, U=100(A+T-K)/T, coverage=100 K/T.
UNKNOWN has no subscore; its unresolved mass remains in [L,U].
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date
import math
from time import perf_counter
from pathlib import Path
import re
import unicodedata
from typing import Any
from functools import lru_cache

from app.services.match_versions import digest
from app.services.compatibility_unspsc import compare as compare_unspsc, catalog

WEIGHTS = {'affinity':25., 'experience':20., 'financial':15., 'technical':15., 'geography':10., 'amount':10., 'preferences':5.}
PROFILE_FIELDS = ('sector','actividades','productos_servicios','keywords','unspsc_codes','departamentos','municipios','presupuesto_min','presupuesto_max','modalidades','experiencia','capacidades','certificaciones')
OPPORTUNITY_FIELDS = ('objeto','descripcion','unspsc_code','departamento','ciudad','valor','modalidad','estado','fecha_cierre','source','cancelled')
STATES = {'VERIFIED_MATCH','VERIFIED_MISMATCH','PARTIAL_MATCH','UNKNOWN','NOT_APPLICABLE'}

@dataclass(frozen=True)
class ModelConfig:
    weights: dict[str,float] = field(default_factory=lambda: dict(WEIGHTS))
    affinity_weights: tuple[float,float,float] = (.5,.3,.2)
    hierarchy: tuple[float,float,float,float] = (1.,.7,.4,.15)
    min_coverage: float = .25
    lexical_gate: float = .20
    semantic_gate: float = .45

    def __post_init__(self):
        if set(self.weights) != set(WEIGHTS) or any(not math.isfinite(v) or v < 0 for v in self.weights.values()) or sum(self.weights.values()) <= 0:
            raise ValueError('Invalid criterion weights')
        for values in (self.affinity_weights, self.hierarchy):
            if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError('Invalid submodel weights')
        if len(self.affinity_weights)!=3 or abs(sum(self.affinity_weights)-1)>1e-9 or len(self.hierarchy)!=4 or tuple(sorted(self.hierarchy,reverse=True)) != self.hierarchy:
            raise ValueError('Invalid hierarchy or affinity weights')
        if any(not math.isfinite(v) or not 0<=v<=1 for v in (self.min_coverage,self.lexical_gate,self.semantic_gate)):
            raise ValueError('Invalid thresholds')


def normalize(value: Any) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').lower()) if not unicodedata.combining(c))

GENERIC = {'servicios','servicio','suministro','contratacion','contrato','empresa','entidad','objeto','publico','publica','general','para','como','segun','mediante','incluye','contratar','prestacion','adquisicion','actividades','productos','sector'}

def terms(text):
    return set(re.findall(r'[a-z0-9]{3,}', normalize(text))) - GENERIC


def lexical(company_text, contract_text):
    left, right = terms(company_text), terms(contract_text)
    if not left or not right:
        return {'score': None, 'matches': [], 'excluded': [], 'phrases': []}
    # Conservative clause-level negation. Excluded terms cannot produce positive affinity.
    excluded = set()
    for clause in re.split(r'[.;\n]', normalize(contract_text) + '\n' + normalize(company_text)):
        if re.search(r'\b(no|se excluye|excepto|sin)\b', clause):
            excluded |= terms(clause)
    matches = (left & right) - excluded
    phrases = sorted(set(' '.join(p) for p in zip(normalize(company_text).split(), normalize(company_text).split()[1:]) if len(terms(' '.join(p)))==2 and ' '.join(p) in normalize(contract_text) and not (terms(' '.join(p)) & excluded)))
    return {'score': len(matches)/len(right), 'matches': sorted(matches), 'excluded': sorted(left & excluded), 'phrases': phrases}


def semantic(pair, company_text, contract_text):
    if not pair or len(pair) != 2:
        return None, 'SEMANTIC_UNAVAILABLE_LEXICAL_ONLY'
    a,b = pair
    if any(p.get('provider') != 'openai' or p.get('model') != 'text-embedding-3-small' or p.get('dimensions') != 1536 or not p.get('version') for p in pair):
        return None, 'SEMANTIC_PROVIDER_OR_MODEL_UNVERIFIED'
    if a['version'] != b['version'] or a.get('text_hash') != digest(company_text) or b.get('text_hash') != digest(contract_text):
        return None, 'SEMANTIC_STALE_INPUT'
    av,bv = a.get('vector',[]),b.get('vector',[])
    if not isinstance(av,list) or not isinstance(bv,list) or len(av)!=1536 or len(bv)!=1536 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in av+bv):
        return None, 'SEMANTIC_INVALID_VECTOR'
    an,bn = math.hypot(*av),math.hypot(*bv)
    if not an or not bn or not math.isfinite(an) or not math.isfinite(bn):
        return None, 'SEMANTIC_ZERO_OR_INVALID_NORM'
    cosine=sum((x/an)*(y/bn) for x,y in zip(av,bv))
    if not math.isfinite(cosine):return None, 'SEMANTIC_INVALID_SIMILARITY'
    return max(0., min(1., cosine)), None


def feature_snapshot(obj, fields):
    values = {k:obj.get(k) if isinstance(obj,dict) else getattr(obj,k,None) for k in fields}
    return {k:v.isoformat() if isinstance(v,date) else v for k,v in values.items()}


def profile_text(profile):
    return ' '.join(str(profile.get(k) or '') if k!='keywords' else ' '.join(profile.get(k) or []) for k in ('sector','actividades','productos_servicios','keywords'))


def contract_text(opportunity):
    return ' '.join(str(opportunity.get(k) or '') for k in ('objeto','descripcion'))


def reviewed(item, as_of):
    """Only trusted, persisted review snapshots can enter this branch; never API claims."""
    review = item.get('review') or {}
    try:
        valid = date.fromisoformat(item['valid_until']) >= as_of
        reviewed_on = date.fromisoformat(review['reviewed_at'][:10]) <= as_of
        valid = valid and date.fromisoformat(item.get('valid_from','1900-01-01')) <= as_of
    except (ValueError,KeyError,TypeError):
        return False
    return bool(item.get('level')=='VERIFIED' and item.get('source_ref') and review.get('reviewer_id') and review.get('document_hash') and valid and reviewed_on)


def requirement_result(req, facts, as_of):
    candidates = [f for f in facts if f.get('key') == req.get('key') and f.get('unit') == req.get('unit')]
    # All contradictory evidence is surfaced, never pick the most favourable fact.
    values = {digest(f.get('value')) for f in candidates}
    if len(values)>1:
        return {'id':req.get('id'), 'state':'UNKNOWN', 'reason':'Contradictory evidence', 'excluding':bool(req.get('excluding')), 'criterion':req.get('criterion')}
    verified = reviewed(req,as_of) and bool(candidates) and all(reviewed(f,as_of) for f in candidates)
    outcome = None
    if verified:
        value, target, operator = candidates[0].get('value'),req.get('value'),req.get('operator')
        if operator == 'eq':
            numeric=all(type(x) in (int,float) and math.isfinite(x) for x in (value,target))
            if numeric or (type(value) is type(target) and type(value) in (str,bool)):
                outcome = value == target
        elif operator in ('gte','lte') and all(type(v) in (int,float) and math.isfinite(v) for v in (value,target)):
            outcome = value >= target if operator == 'gte' else value <= target
    state = ('VERIFIED_MATCH' if outcome else 'VERIFIED_MISMATCH') if outcome is not None else 'UNKNOWN'
    return {'id':req.get('id'), 'state':state, 'reason':'Reviewed comparison' if outcome is not None else 'Requirement or evidence pending verification', 'excluding':bool(req.get('excluding')), 'criterion':req.get('criterion'), 'company_value':candidates[0].get('value') if candidates else None, 'contract_value':req.get('value'), 'source':{'requirement':req.get('source_ref'), 'evidence':[f.get('source_ref') for f in candidates]}}


def eligibility(requirements, facts, checklist, as_of):
    comparisons = [requirement_result(r,facts,as_of) for r in sorted(requirements,key=lambda r:str(r.get('id')))]
    if any(r['excluding'] and r['state']=='VERIFIED_MISMATCH' for r in comparisons):
        state = 'NOT_ELIGIBLE_VERIFIED'
    elif not comparisons:
        state = 'NOT_EVALUABLE'
    elif all(r.get('id') for r in requirements) and len({r['id'] for r in requirements})==len(requirements) and reviewed(checklist,as_of) and checklist.get('complete') is True and all(r['state']=='VERIFIED_MATCH' for r in comparisons):
        state = 'ELIGIBLE_VERIFIED'
    else:
        state = 'PENDING_VERIFICATION'
    return state, comparisons


def criterion(key, weight, score=None, information=0., reason='Información insuficiente', state=None, company=None, contract=None, source=None):
    if score is not None and (not math.isfinite(score) or not 0<=score<=1):
        raise ValueError('Invalid subscore')
    if not 0<=information<=1 or (score is None and information):
        raise ValueError('Invalid information mass')
    state = state or ('PARTIAL_MATCH' if score is not None else 'UNKNOWN')
    if state not in STATES or (state in ('UNKNOWN','NOT_APPLICABLE') and score is not None):
        raise ValueError('Invalid criterion state')
    return {'criterion':key,'weight':weight,'state':state,'subscore':score,'information_fraction':information,'contribution':weight*information*score if score is not None else None,'reason':reason,'company_value':company,'contract_value':contract,'source':source or []}


def aggregate(criteria):
    total = sum(c['weight'] for c in criteria if c['state']!='NOT_APPLICABLE')
    known = sum(c['weight']*c['information_fraction'] for c in criteria if c['state']!='NOT_APPLICABLE')
    supported = sum(c['contribution'] or 0 for c in criteria if c['state']!='NOT_APPLICABLE')
    return {'lower':100*supported/total if total else None, 'upper':100*(supported+total-known)/total if total else None, 'coverage':100*known/total if total else 0., 'observed_affinity':100*supported/known if known else None, 'applicable_weight':total}


@lru_cache(maxsize=32)
def _model_version(config_digest):
    files = ('compatibility_v2.py','compatibility_unspsc.py')
    return digest(['compatibility-v2-experimental-1',config_digest,catalog(),[Path(__file__).with_name(f).read_text() for f in files]])

def model_version(config):
    return _model_version(digest(asdict(config)))


def evaluate(profile: dict, opportunity: dict, *, evidence: dict|None=None, requirements: list|None=None, checklist: dict|None=None, semantic_pair=None, config: ModelConfig|None=None, as_of: date, timings: dict|None=None):
    started=perf_counter()
    def lap(name):
        nonlocal started
        now=perf_counter()
        if timings is not None:timings[name]=(now-started)*1000
        started=now
    config = config or ModelConfig()
    evidence,requirements,checklist = evidence or {},requirements or [],checklist or {}
    company_text, object_text = profile_text(profile),contract_text(opportunity)
    lap('features')
    lex = lexical(company_text,object_text)
    sem,warning = semantic(semantic_pair,company_text,object_text)
    uns = compare_unspsc(profile.get('unspsc_codes') or [],opportunity.get('unspsc_code'),config.hierarchy)
    components = [lex['score'],sem,uns['score']]
    info = sum(w for w,s in zip(config.affinity_weights,components) if s is not None)
    sub = sum(w*s for w,s in zip(config.affinity_weights,components) if s is not None)/info if info else None
    criteria = [criterion('affinity',config.weights['affinity'],sub,info, 'Componentes disponibles: '+', '.join(name for name,score in zip(('léxico','semántico real','UNSPSC'),components) if score is not None)+'; componentes ausentes conservan masa desconocida',company={'text':company_text,'codes':profile.get('unspsc_codes')},contract={'text':object_text,'code':opportunity.get('unspsc_code')},source={'lexical':lex,'semantic_score':sem,'unspsc':uns})]
    lap('affinity')
    elig, comparisons = eligibility(requirements,evidence.get('facts') or [],checklist,as_of)
    lap('eligibility')
    for key in ('experience','financial','technical'):
        rows = [r for r in comparisons if r['criterion']==key]
        known = [r for r in rows if r['state'] in ('VERIFIED_MATCH','VERIFIED_MISMATCH')]
        na = (evidence.get('not_applicable') or {}).get(key,{})
        if not rows and reviewed(na,as_of) and na.get('reason'):
            criteria.append(criterion(key,config.weights[key],state='NOT_APPLICABLE',reason=na['reason'],source=na.get('source_ref')))
        else:
            score = sum(r['state']=='VERIFIED_MATCH' for r in known)/len(known) if known else None
            state = ('VERIFIED_MATCH' if score==1 else 'VERIFIED_MISMATCH') if known and len(known)==len(rows) and score in (0,1) else None
            criteria.append(criterion(key,config.weights[key],score,len(known)/len(rows) if rows else 0.,state=state,reason='Comparación de requisitos y evidencia revisados; texto libre no acredita capacidad',source=rows))
    places = {normalize(p) for p in profile.get('departamentos') or [] if p}
    place = normalize(opportunity.get('departamento'))
    score = float(place in places) if places and place else None
    criteria.append(criterion('geography',config.weights['geography'],score,float(score is not None),reason='Cobertura departamental declarada; no certifica capacidad operativa',company=sorted(places),contract=place,source=['profile.departamentos','opportunity.departamento']))
    low, high, value = profile.get('presupuesto_min'),profile.get('presupuesto_max'),opportunity.get('valor')
    valid = lambda v: type(v) in (int,float) and math.isfinite(v) and v>=0
    valid_range = (low is not None or high is not None) and all(v is None or valid(v) for v in (low,high)) and not (low is not None and high is not None and low>high)
    score = float((low is None or value>=low) and (high is None or value<=high)) if valid_range and valid(value) else None
    criteria.append(criterion('amount',config.weights['amount'],score,float(score is not None),reason='Preferencia comercial declarada; no es capacidad financiera',company={'min':low,'max':high},contract=value,source=['profile.presupuesto','opportunity.valor']))
    prefs = {normalize(p) for p in profile.get('modalidades') or [] if p}
    modality = normalize(opportunity.get('modalidad'))
    score = float(modality in prefs) if prefs and modality else None
    criteria.append(criterion('preferences',config.weights['preferences'],score,float(score is not None),reason='Preferencia declarada de modalidad',company=sorted(prefs),contract=modality,source=['profile.modalidades','opportunity.modalidad']))
    lap('criteria')
    summary = aggregate(criteria)
    gate = (lex['score'] is not None and lex['score']>=config.lexical_gate) or (sem is not None and sem>=config.semantic_gate) or uns['level'] in ('CLASS','PRODUCT')
    status = 'INSUFFICIENT_CONTRACTUAL_AFFINITY' if not gate else ('INSUFFICIENT_INFORMATION' if summary['coverage']<100*config.min_coverage else ('COMPLETE' if summary['coverage']>=100-1e-9 else 'PROVISIONAL'))
    version = model_version(config)
    for item in criteria:
        item['normalized_contribution']=100*(item['contribution'] or 0)/summary['applicable_weight'] if item['contribution'] is not None and summary['applicable_weight'] else None
        item['evaluated_at']=as_of.isoformat()
        item['model_version']=version
    input_versions = {'profile':digest(profile),'opportunity':digest(opportunity),'evidence':digest(evidence),'requirements':digest([requirements,checklist]),'semantic':digest(semantic_pair),'as_of':as_of.isoformat()}
    lap('aggregation_versioning')
    evidence_summary={'experience':{'declared_text':bool(profile.get('experiencia')),'structured_facts':sum(f.get('category')=='experience' for f in evidence.get('facts',[])),'documented_observations':len(evidence.get('observations',[])),'verified_facts':sum(f.get('category')=='experience' and reviewed(f,as_of) for f in evidence.get('facts',[])),'warning':'Declaración, estructura y documento no equivalen a acreditación verificada'}}
    return {'evidence_summary':evidence_summary,'compatibility_score':summary['lower'] if status in ('COMPLETE','PROVISIONAL') else None,'score_status':status,'eligibility_status':elig,'evidence_coverage':summary['coverage'],'normalization_weight':summary['applicable_weight'],'sensitivity_interval':{'lower':summary['lower'],'upper':summary['upper']},'observed_affinity':summary['observed_affinity'],'criteria':criteria,'requirements':comparisons,'pending_requirements':[r['id'] for r in comparisons if r['state']=='UNKNOWN'],'explanations':[{'criterion':c['criterion'],'reason':c['reason'],'contribution':c['contribution'],'normalized_contribution':c['normalized_contribution']} for c in criteria],'warnings':[w for w in [warning,'Índice experimental, no probabilidad de adjudicación ni certificación jurídica.', 'Participación no recomendada automáticamente; verificar requisitos habilitantes.'] if w], 'recommend_participation':False,'model_version':version,'input_versions':input_versions,'evaluated_at':as_of.isoformat()}
