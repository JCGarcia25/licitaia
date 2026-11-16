"""Mathematical properties over reproducible generated fixtures; no human labels."""
from copy import deepcopy
from datetime import date
import random
import pytest
from app.services import compatibility_v2 as v
from app.services.compatibility_unspsc import compare, members

DAY=date(2026,11,15)
P={'sector':'software','actividades':'desarrollo software','keywords':['aplicaciones'],'departamentos':['Meta'],'presupuesto_min':1,'presupuesto_max':1000,'modalidades':['Licitación'],'unspsc_codes':['81111501']}
O={'objeto':'desarrollo software aplicaciones','departamento':'Meta','valor':100,'modalidad':'Licitacion','unspsc_code':'81111501'}

def result(p=None,o=None,**kw):return v.evaluate(p or P,o or O,as_of=DAY,**kw)

def reviewed(**kw):
    return dict(level='VERIFIED',source_ref='private:document:1:page:1',valid_until='2027-01-01',review={'reviewer_id':'trusted-reviewer','reviewed_at':'2026-01-01','document_hash':'abc'},**kw)

def test_unknown_no_inflation_and_explanations():
    r=result()
    assert r['compatibility_score']<=42.5
    assert r['score_status']=='PROVISIONAL'
    assert r['eligibility_status']=='NOT_EVALUABLE'
    assert r['sensitivity_interval']['upper']>r['compatibility_score']
    assert sum(c['normalized_contribution'] or 0 for c in r['criteria'])==pytest.approx(r['sensitivity_interval']['lower'])
    for c in r['criteria']:
        if c['state']=='UNKNOWN':assert c['subscore'] is None and c['contribution'] is None
        assert next(x for x in r['explanations'] if x['criterion']==c['criterion'])['contribution']==c['contribution']
    assert any('LEXICAL' in w for w in r['warnings'])

def test_no_contractual_affinity_even_with_location_budget():
    r=result(o={**O,'objeto':'cirugía hospitalaria','unspsc_code':None})
    assert r['compatibility_score'] is None
    assert r['score_status']=='INSUFFICIENT_CONTRACTUAL_AFFINITY'


def test_fake_stale_bad_vectors_rejected():
    a={'provider':'fake','model':'hash','vector':[1.,0.]}
    assert v.semantic([a,a],'a','b')[0] is None
    a={'provider':'openai','model':'text-embedding-3-small','dimensions':1536,'version':'v1','text_hash':v.digest('a'),'vector':[1.]+[0.]*1535}
    b={**a,'text_hash':v.digest('b')}
    assert v.semantic([a,b],'a','b')[0]==1
    assert v.semantic([a,b],'changed','b')[0] is None
    b['vector']=[1e308]*1536
    assert v.semantic([a,b],'a','b')[0] is None
    b['vector']=[float('nan')]*1536
    assert v.semantic([a,b],'a','b')[0] is None


def test_lexical_normalization_negation_phrases():
    assert v.lexical('cirugia especializada','Cirugía especializada')['score']==1
    assert v.lexical('software contable','No incluye software contable. Obras civiles')['score']==0
    assert v.lexical('software contable','software contable')['phrases']==['software contable']


def test_unspsc_verified_hierarchy_and_aggregate():
    assert '81111501' in members()
    assert compare(['81111501'],'81111501')['relation']=='EXACT'
    assert compare(['81111500'],'81111501')['level']=='CLASS'
    assert compare(['81110000'],'81111501')['level']=='FAMILY'
    assert compare(['81000000'],'81111501')['level']=='SEGMENT'
    assert compare(['99999999'],'81111501')['score'] is None
    assert compare(['81111501'],'10101501')['relation']=='NONE'
    assert compare(['81111501','81110000'],'81111501')==compare(['81110000','81111501'],'81111501')


def test_declared_experience_never_verified():
    req=reviewed(id='liquidity',criterion='financial',key='liquidity',value=2.,unit='ratio',operator='gte',excluding=True)
    fact={'key':'liquidity','value':3.,'unit':'ratio','level':'STRUCTURED'}
    r=result(evidence={'facts':[fact]},requirements=[req])
    assert r['eligibility_status']=='PENDING_VERIFICATION'
    assert next(c for c in r['criteria'] if c['criterion']=='financial')['state']=='UNKNOWN'


def test_excluding_failure_not_compensated_and_complete_review():
    req=reviewed(id='liquidity',criterion='financial',key='liquidity',value=2.,unit='ratio',operator='gte',excluding=True)
    fact=reviewed(key='liquidity',value=1.,unit='ratio')
    r=result(evidence={'facts':[fact]},requirements=[req],checklist=reviewed(complete=True))
    assert r['eligibility_status']=='NOT_ELIGIBLE_VERIFIED' and not r['recommend_participation']
    assert r['compatibility_score'] is not None  # Affinity remains independent.
    fact['value']=3.
    r=result(evidence={'facts':[fact]},requirements=[req],checklist=reviewed(complete=True))
    assert r['eligibility_status']=='ELIGIBLE_VERIFIED'
    r=result(evidence={'facts':[fact]},requirements=[req])
    assert r['eligibility_status']=='PENDING_VERIFICATION'
    fact['valid_until']='2025-01-01'
    assert result(evidence={'facts':[fact]},requirements=[req],checklist=reviewed(complete=True))['eligibility_status']=='PENDING_VERIFICATION'


def test_contradictory_facts_and_unsupported_na():
    req=reviewed(id='x',criterion='technical',key='certification',value=True,unit=None,operator='eq')
    facts=[reviewed(key='certification',value=x,unit=None) for x in (True,False)]
    r=result(evidence={'facts':facts,'not_applicable':{'experience':{'reason':'claimed'}}},requirements=[req])
    assert r['requirements'][0]['state']=='UNKNOWN'
    assert next(c for c in r['criteria'] if c['criterion']=='experience')['state']=='UNKNOWN'
    r=result(evidence={'not_applicable':{'experience':reviewed(reason='Reviewed non-applicability')}})
    assert next(c for c in r['criteria'] if c['criterion']=='experience')['state']=='NOT_APPLICABLE'


def test_properties_bounds_monotonicity_unknown_intervals_and_determinism():
    rng=random.Random(42)
    for _ in range(250):
        weights=[rng.random()*100 for _ in range(7)]
        scores=[rng.random() for _ in weights]
        criteria=[v.criterion(k,w,s,1.) for k,w,s in zip(v.WEIGHTS,weights,scores)]
        a=v.aggregate(criteria)
        assert 0<=a['lower']<=100 and a['lower']==pytest.approx(a['upper'])
        index=rng.randrange(7); better=deepcopy(criteria)
        better[index]['subscore']=1.; better[index]['contribution']=better[index]['weight']
        assert v.aggregate(better)['lower']>=a['lower']-1e-10
        unknown=deepcopy(criteria); unknown[index]=v.criterion(unknown[index]['criterion'],unknown[index]['weight'])
        b=v.aggregate(unknown)
        assert b['lower']<=a['lower']+1e-10 and b['upper']>=a['upper']-1e-10
        assert b['coverage']<=a['coverage']+1e-10
        shuffled=criteria[:];rng.shuffle(shuffled)
        assert v.aggregate(shuffled)['lower']==pytest.approx(a['lower'])
    assert result()==result()
    assert result(p={**P,'departamentos':['Meta','Cauca']})['compatibility_score']==result(p={**P,'departamentos':['Cauca','Meta']})['compatibility_score']


def test_versions_configuration_and_inputs():
    r=result();config=v.ModelConfig(weights={**v.WEIGHTS,'affinity':26})
    assert result(config=config)['model_version']!=r['model_version']
    assert result(p={**P,'certificaciones':['ISO']})['input_versions']!=r['input_versions']
    for weights in ({}, {**v.WEIGHTS,'amount':-1},{**v.WEIGHTS,'amount':float('nan')}):
        with pytest.raises(ValueError):v.ModelConfig(weights=weights)
    assert result(p={**P,'presupuesto_min':2000,'presupuesto_max':1})['criteria'][5]['state']=='UNKNOWN'


def test_reviewed_values_must_be_comparable_not_coerced():
    req=reviewed(id='x',criterion='technical',key='count',unit='units',operator='eq',value=3)
    fact=reviewed(key='count',unit='units',value=3.)
    assert v.requirement_result(req,[fact],DAY)['state']=='VERIFIED_MATCH'
    fact['value']='3'
    assert v.requirement_result(req,[fact],DAY)['state']=='UNKNOWN'
