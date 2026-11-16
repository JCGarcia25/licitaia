"""Bounded actual algorithms on synthetic inputs; no production inference or human labels."""
from datetime import date
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.services import compatibility_v2 as v
from app.services.matcher import score_opportunity
from app.services.embeddings import embed
from app.services.match_versions import algorithm_version


def main():
    count=int(sys.argv[1]) if len(sys.argv)>1 else 20
    if not 1<=count<=100:raise SystemExit('Bounded diagnostic: 1..100 pairs')
    s=get_settings()
    if s.environment not in {'testing','isolated-integration'} or s.embedding_provider!='fake':raise SystemExit('Testing + fake provider required; no external calls')
    p={'sector':'software','actividades':'software contable','productos_servicios':'aplicaciones','keywords':['software'],'departamentos':['Meta'],'presupuesto_min':1,'presupuesto_max':10000000,'unspsc_codes':['81111501'],'modalidades':['Licitación']}
    vector=embed('software software contable aplicaciones software')
    times={'legacy':[],'v2':[]};components={};pairs=[]
    for i in range(count):
        o={'objeto':'software contable' if i%2 else 'herramientas agrícolas','descripcion':'diagnóstico sintético','valor':1000000,'departamento':'Meta','modalidad':'Licitación','estado':'En proceso','unspsc_code':'81111501' if i%2 else '10101501'}
        o['_vector']=embed(f"{o['objeto']} {o['descripcion']}")
        start=perf_counter();old=score_opportunity(p,o,profile_vector=vector);times['legacy'].append((perf_counter()-start)*1000)
        start=perf_counter();measurement={};new=v.evaluate(p,{k:value for k,value in o.items() if k!='_vector'},as_of=date(2026,11,15),timings=measurement);times['v2'].append((perf_counter()-start)*1000)
        for key,value in measurement.items():components.setdefault(key,[]).append(value)
        pairs.append({'pair':i,'legacy':old.score,'v2':new['compatibility_score'],'coverage':new['evidence_coverage'],'eligibility':new['eligibility_status']})
    def summary(items):return {'mean_ms':statistics.mean(items),'p95_ms':sorted(items)[max(0,int(.95*len(items))-1)],'first_ms':items[0]}
    print(json.dumps({'fixture':'SYNTHETIC_NO_HUMAN_LABELS','count':count,'cost_scope':'CPU pure algorithms only; precomputed fake legacy vectors; V2 lexical+verified numeric UNSPSC, semantic unavailable; no DB/network/LLM','versions':{'legacy':algorithm_version(),'v2':new['model_version']},'timings':{key:summary(values) for key,values in times.items()},'components':{key:summary(values) for key,values in components.items()},'pairs':pairs,'superiority_demonstrated':False},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
