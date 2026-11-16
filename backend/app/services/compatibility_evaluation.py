"""Paired offline evaluation; never fabricates labels or promotes a model."""
from collections import defaultdict
import math
import random
from statistics import mean
from app.services.ranking_evaluation import evaluate

METRICS=('precision_at_5','precision_at_10','ndcg_at_10','recall_at_20','false_positive_rate')
PREDECLARED={'pilot_pairs':100,'minimum_independent_clusters':20,'bootstrap_replicates':2000,'primary':'precision_at_10 delta >= 0; require CI lower >= 0 before considering non-inferiority','secondary':'Traceability, evidence coverage, unsupported high scores, sector results and bounded operational costs require separate review','activation':'Never automatic; no superiority claim without independent human validation'}


def compare(legacy,v2,judgments,queries,*,seed=20261115,allow_synthetic=False):
    def index(rows):
        result={(r['query_id'],r['opportunity_id']):r for r in rows}
        if len(result)!=len(rows):raise ValueError('Duplicate paired predictions')
        return result
    left,right=index(legacy),index(v2)
    if set(left)!=set(right):raise ValueError('Both engines must cover identical input pairs, including null results')
    manifest={q['query_id']:q for q in queries}
    if len(manifest)!=len(queries):raise ValueError('Duplicate query')
    for key,a in left.items():
        b=right[key]; q=manifest.get(key[0],{})
        if not q.get('snapshot_at') or not q.get('company_cluster_id'):raise ValueError('Require frozen window and private anonymous company cluster')
        for field in ('profile_version','opportunity_version','snapshot_at'):
            if not a.get(field) or a.get(field)!=b.get(field):raise ValueError('Unpaired input versions or temporal window')
        if a['snapshot_at']!=q['snapshot_at']:raise ValueError('Window differs from query manifest')
    reports={name:evaluate(rows,judgments,queries,allow_synthetic=allow_synthetic) for name,rows in (('legacy',legacy),('v2',v2))}
    clusters=defaultdict(list)
    byid={name:{q['query_id']:q for q in report['queries']} for name,report in reports.items()}
    for q in queries:
        clusters[q['company_cluster_id']].append(q['query_id'])
    human_count=reports['v2']['human_judgment_count']
    verified_clusters=bool(queries) and all(q.get('cluster_identity_verified',True) is True for q in queries)
    sufficient=human_count>=PREDECLARED['pilot_pairs'] and len(clusters)>=PREDECLARED['minimum_independent_clusters'] and verified_clusters
    def interval(qids,metric):
        # Cluster resampling preserves dependency between repeated company queries.
        groups=[]
        for ids in clusters.values():
            values=[byid['v2'][qid][metric]-byid['legacy'][qid][metric] for qid in ids if qid in qids and byid['v2'][qid][metric] is not None and byid['legacy'][qid][metric] is not None]
            if values:groups.append(values)
        if not sufficient or len(groups)<20:return {'delta':None,'ci95':None,'clusters':len(groups),'status':'UNVERIFIED_COMPANY_IDENTITIES' if not verified_clusters else 'INSUFFICIENT_HUMAN_SAMPLE'}
        rng=random.Random(seed); samples=[]
        for _ in range(PREDECLARED['bootstrap_replicates']):
            draw=[rng.choice(groups) for _ in groups]
            samples.append(mean([v for group in draw for v in group]))
        samples.sort()
        return {'delta':mean([v for group in groups for v in group]),'ci95':[samples[int(.025*len(samples))],samples[int(.975*len(samples))]],'clusters':len(groups),'status':'ESTIMATED_CLUSTER_BOOTSTRAP'}
    deltas={m:interval(set(manifest),m) for m in METRICS}
    sector={sector:{m:interval({q['query_id'] for q in queries if q.get('sector','unspecified')==sector},m) for m in METRICS} for sector in sorted({q.get('sector','unspecified') for q in queries})}
    coverage=[]
    for r in v2:
        value=r.get('evidence_coverage')
        if value is not None:
            if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100:raise ValueError('Invalid evidence coverage')
            coverage.append(value)
    return {'cluster_identity_condition':'SATISFIED_BY_MANIFEST' if verified_clusters else 'UNVERIFIED_IDENTITIES_PRESENT','status':'HUMAN_PAIRED_ESTIMATES' if sufficient else ('PENDING_VERIFIED_COMPANY_IDENTITIES' if human_count>=PREDECLARED['pilot_pairs'] and not verified_clusters else 'PENDING_SUFFICIENT_HUMAN_LABELS'),'criteria_predeclared':PREDECLARED,'reports':reports,'paired_deltas':deltas,'by_sector_deltas':sector,'mean_evidence_coverage':mean(coverage) if coverage else None,'non_evaluable_rate':sum(r.get('score') is None for r in v2)/len(v2) if v2 else None,'promotion_authorized':False,'warning':'Pilot size does not guarantee power. Sensitivity intervals are not statistical confidence intervals. Human affinity, eligibility and evidence quality must be labeled separately.'}
