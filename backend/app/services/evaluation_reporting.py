"""Sealed comparison A/B/C; no claims from incomplete or synthetic evidence."""
from collections import defaultdict,Counter
from statistics import mean
from app.db.models import EvaluationSample as Sample,EvaluationAssignment as Assignment,EvaluationJudgment as Judgment,EvaluationAdjudication as Adjudication,EvaluationReport as Report,EvaluationExposure as Exposure
from app.services.evaluation_guard import require_environment
from app.services.compatibility_evaluation import compare
from app.services.evaluation_platform import now,audit,signature
from app.services.match_versions import digest


def agreement(pairs):
    if not pairs:return {'n':0,'raw_agreement':None,'quadratic_weighted_kappa':None}
    n=len(pairs);a=Counter(x for x,y in pairs);b=Counter(y for x,y in pairs)
    observed=sum((x-y)**2/9 for x,y in pairs)/n
    expected=sum(a[i]*b[j]*(i-j)**2/9 for i in range(4) for j in range(4))/n**2
    return {'n':n,'raw_agreement':sum(x==y for x,y in pairs)/n,'quadratic_weighted_kappa':1-observed/expected if expected else None,'warning':'Descriptive agreement; no confidence interval claimed'}


def build(db,c):
    samples=db.query(Sample).filter_by(campaign_id=c.id).all();sids=[s.id for s in samples]
    assignments=db.query(Assignment).filter(Assignment.sample_id.in_(sids)).all();byassignment={a.id:a for a in assignments}
    judgments=db.query(Judgment).filter(Judgment.assignment_id.in_(list(byassignment))).all()
    js=defaultdict(list)
    for j in judgments:
        a=byassignment[j.assignment_id]
        if a.kind=='REVIEW':js[a.sample_id].append(j)
    resolutions={r.sample_id:r for r in db.query(Adjudication).filter(Adjudication.sample_id.in_(sids))}
    labels=[];pairs=[];unresolved=[];scope='synthetic_test' if c.data_scope=='synthetic' else 'human'
    sample_by_key={s.pair_key:s for s in samples}
    for sample in samples:
        primary=js[sample.id]
        if len(primary)==2:pairs.append(tuple(j.payload['relevance'] for j in primary))
        final=resolutions.get(sample.id)
        if not final and len(primary)==2 and signature(primary[0].payload)==signature(primary[1].payload):final=primary[0]
        if not final:unresolved.append(sample.id);continue
        row=sample.snapshot;payload=final.payload
        labels.append({'query_id':row['query_id'],'opportunity_id':row['pair_key'],'relevance':payload['relevance'],'profile_version':row['profile_version'],'opportunity_version':row['opportunity_version'],'label_source':scope,'blinded':True,'reason':payload['reason'],'evaluator_id':digest(['reviewer',final.assignment_id]),'evaluated_at':final.created_at.isoformat(),'eligibility':payload['eligibility'],'evidence_quality':payload['evidence_quality']})
    selected_frame=set(c.selection['frame_keys']);universe=[r for r in c.universe if r['pair_key'] in selected_frame]
    def evaluate_partition(partition):
        # Include the full declared frame for each query, not only sampled/judged rows.
        chosen_queries={s.snapshot['query_id'] for s in samples if s.split==partition}
        rows=[r for r in universe if r['query_id'] in chosen_queries]
        manifests={}
        predictions={m:[] for m in 'ABC'}
        for row in rows:
            qid=row['query_id'];manifest=manifests.setdefault(qid,{'query_id':qid,'company_cluster_id':row['company_cluster_id'],'cluster_identity_verified':row.get('company_cluster_basis')=='existing-organization','sector':row['profile'].get('sector') or 'unspecified','snapshot_at':c.config['snapshot_at'],'universe_ids':[],'universe_complete':True,'ranking_complete':True,'require_complete_execution':True})
            manifest['universe_ids'].append(row['pair_key'])
            for model in 'ABC':
                value=row['predictions'][model]
                predictions[model].append({'query_id':qid,'opportunity_id':row['pair_key'],'score':value.get('score'),'algorithm_version':value['algorithm_version'],'profile_version':row['profile_version'],'opportunity_version':row['opportunity_version'],'snapshot_at':c.config['snapshot_at'],'evidence_coverage':value.get('evidence_coverage'),'computed':(model=='A' and value.get('score') is not None) or bool(value.get('result'))})
        relevant_labels=[j for j in labels if j['query_id'] in manifests]
        result={'A_vs_B':compare(predictions['A'],predictions['B'],relevant_labels,list(manifests.values()),allow_synthetic=scope=='synthetic_test'),'B_vs_C':compare(predictions['B'],predictions['C'],relevant_labels,list(manifests.values()),allow_synthetic=scope=='synthetic_test')}
        # Modality is an explicitly conditional ranking within the same frozen query.
        by_modality={}
        for modality in sorted({r['opportunity'].get('modalidad') or 'UNKNOWN' for r in rows}):
            subset=[r for r in rows if (r['opportunity'].get('modalidad') or 'UNKNOWN')==modality];keys={r['pair_key'] for r in subset}
            qs=[]
            for q in manifests.values():
                ids=[k for k in q['universe_ids'] if k in keys]
                if ids:qs.append({**q,'universe_ids':ids})
            by_modality[modality]=compare([p for p in predictions['A'] if p['opportunity_id'] in keys],[p for p in predictions['B'] if p['opportunity_id'] in keys],[j for j in relevant_labels if j['opportunity_id'] in keys],qs,allow_synthetic=scope=='synthetic_test')
        result['conditional_modality_rankings']=by_modality
        result['campaign_primary_rule']={'material_p10_margin':c.config['rubric']['material_p10_margin'],'decision_scope':'sealed holdout only; source compare criterion with zero margin is descriptive legacy context'}
        return result
    ranks={m:{} for m in 'ABC'};query_sizes=Counter(r['query_id'] for r in universe)
    for model in 'ABC':
        grouped=defaultdict(list)
        for row in universe:
            if row['predictions'][model].get('score') is not None:grouped[row['query_id']].append(row)
        for qid,rows in grouped.items():
            for position,row in enumerate(sorted(rows,key=lambda r:(r['predictions'][model]['score'],r['pair_key']),reverse=True),1):ranks[model][(qid,row['pair_key'])]=position
    cases=[];labelby={(j['query_id'],j['opportunity_id']):j for j in labels}
    for row in universe:
        j=labelby.get((row['query_id'],row['pair_key']))
        if not j:continue
        a,b=row['predictions']['A'].get('score'),row['predictions']['B'].get('score')
        key=(row['query_id'],row['pair_key']);ra=ranks['A'].get(key);rb=ranks['B'].get(key);rc=ranks['C'].get(key)
        improvement=rank_change(ra,rb,j['relevance'],query_sizes[row['query_id']])
        cases.append({'rank_A':ra,'rank_B':rb,'rank_C':rc,'direction_B_vs_A':improvement,'direction_C_vs_B':rank_change(rb,rc,j['relevance'],query_sizes[row['query_id']]) if row['predictions']['C'].get('status')=='REAL_PROVIDER' else 'NOT_EVALUABLE','pair_alias':row['pair_key'],'relevance':j['relevance'],'legacy_score':a,'v2_score':b,'semantic_score':row['predictions']['C'].get('score'),'semantic_status':row['predictions']['C'].get('status'),'difference':b-a if a is not None and b is not None else None,'false_positive':j['relevance']<2 and b is not None and b>=c.config['rubric']['positive_score_threshold'],'false_negative':j['relevance']>=2 and (b is None or b<c.config['rubric']['positive_score_threshold']),'error_classification':'MISSING_INFORMATION' if b is None else 'SCORING_REVIEW_REQUIRED','retrieval_origin':row.get('retrieval_origin'),'eligibility_opinion':j['eligibility'],'evidence_quality_opinion':j['evidence_quality']})
    partitions={p:evaluate_partition(p) for p in ('development','holdout')}
    criterion={'ranking_noninferiority':'INCONCLUSIVE','unsupported_high_recommendations':'NOT_EVALUABLE','insufficient_information_explicit':'TECHNICALLY_TESTED','isolation_and_traceability':'TECHNICALLY_TESTED','semantic_cost_benefit':'NOT_EVALUABLE','verified_eligibility_safety':'NOT_EVALUABLE','operational_sustainability':'NOT_EVALUABLE'}
    holdout=partitions['holdout']['A_vs_B']['paired_deltas']['precision_at_10']
    holdout_query_ids={s.snapshot['query_id'] for s in samples if s.split=='holdout'}
    holdout_rows=[r for r in universe if r['query_id'] in holdout_query_ids]
    full_execution={m:bool(holdout_rows) and all((r['predictions'][m].get('score') is not None if m=='A' else bool(r['predictions'][m].get('result'))) for r in holdout_rows) for m in 'ABC'}
    margin=c.config['rubric']['material_p10_margin']
    if scope=='human' and holdout['ci95'] is not None and full_execution['A'] and full_execution['B']:
        low,high=holdout['ci95']
        criterion['ranking_noninferiority']='FULFILLED' if low>=-margin else ('NOT_FULFILLED' if high < -margin else 'INCONCLUSIVE')
    semantic_ci=partitions['holdout']['B_vs_C']['paired_deltas']['precision_at_10']['ci95']
    if scope=='human' and semantic_ci is not None and full_execution['B'] and full_execution['C']:
        criterion['semantic_cost_benefit']='FULFILLED' if semantic_ci[0]>0 and c.reserved_cost<=c.config['max_cost_usd'] else ('NOT_FULFILLED' if semantic_ci[1]<=0 else 'INCONCLUSIVE')
    from app.db.models import EvaluationEmbedding
    usage=db.query(EvaluationEmbedding).filter_by(campaign_id=c.id).all()
    consumption={'calls_reserved':c.external_calls,'maximum_reserved_cost_usd':c.reserved_cost,'known_tokens':sum(r.usage_tokens or 0 for r in usage),'known_estimated_cost_usd':sum(r.estimated_cost or 0 for r in usage),'unknown_usage_reservations':sum(r.usage_tokens is None for r in usage),'tariff_usd_per_million_tokens':c.config.get('tariff_usd_per_million_tokens')}
    # No automatic verdict on operation, legal safety or extrapolation from samples.
    status='SYNTHETIC_PROCEDURE_ONLY' if scope=='synthetic_test' else ('PAIRED_HOLDOUT_ESTIMATES' if holdout['ci95'] is not None else 'INCONCLUSIVE')
    versions={'pipeline':c.config['pipeline_version'],'v2':c.config['model_version'],'rubric':c.config['criteria_version'],'input_universe':c.config['universe_hash'],'selection':digest(c.selection),'snapshot_at':c.config['snapshot_at'],'legacy_algorithms':sorted({r['predictions']['A']['algorithm_version'] for r in universe})}
    sampling={'retrieval_groups_available':c.selection.get('retrieval_groups_available',{}),'retrieval_groups_selected':c.selection.get('retrieval_groups_selected',{}),'probability_scope':c.selection.get('probability_scope'),'organization_grouping':dict(Counter(r.get('company_cluster_basis','synthetic-test-identity') for r in universe)),'seed':c.selection['seed'],'submitted_pairs':c.selection['submitted_pairs'],'frame_pairs':c.selection['frame_pairs'],'selected_pairs':len(c.selection['selected']),'duplicate_process_pairs_excluded':len(c.selection['duplicate_process_pairs_excluded']),'holdout_companies':len(c.selection['holdout_clusters'])}
    return {'versions':versions,'sampling':sampling,'holdout_execution_complete':full_execution,'conditional_estimate_warning':'Any incomplete-arm query is withheld; conditional CIs from executable subsets do not authorize a whole-holdout conclusion.','semantic_consumption':consumption,'campaign_alias':digest(c.id),'dataset_scope':c.data_scope,'status':status,'statistical_conclusion':'INCONCLUSIVE' if scope=='synthetic_test' or holdout['ci95'] is None else criterion['ranking_noninferiority'],'criteria_predeclared':c.config['rubric'],'partitions':partitions,'agreement':agreement(pairs),'resolved_pairs':len(labels),'unresolved_pairs':len(unresolved),'human_label_count':len(labels) if scope=='human' else 0,'synthetic_test_labels':len(labels) if scope=='synthetic_test' else 0,'sample_coverage':len(labels)/len(samples) if samples else None,'cases':cases,'conditional_improvements':[x['pair_alias'] for x in cases if x['direction_B_vs_A']=='IMPROVES'],'conditional_regressions':[x['pair_alias'] for x in cases if x['direction_B_vs_A']=='WORSENS'],'retrieval_attribution':'NOT_EVALUABLE without audited retrieval traces; provenance alone is not causal evidence','success_criteria':criterion,'activation_authorized':False,'warning':'Metrics apply to the declared deduplicated frame, not all SECOP. Sampling does not provide complete labels for unsampled top results. No causal attribution of recovery/scoring errors without independent retrieval review. No commercial superiority from synthetic cases.'}


def close(db,c,actor):
    require_environment(db)
    if c.state!='READY':raise ValueError('Only frozen ready campaigns may close')
    if db.query(Report.id).filter_by(campaign_id=c.id).first():raise ValueError('Report sealed')
    # Caller locks campaign so new submissions cannot race with closure.
    payload=build(db,c);c.state='CLOSED';c.closed_at=now()
    from uuid import uuid4
    r=Report(id=str(uuid4()),campaign_id=c.id,payload=payload,version=digest(payload));db.add(r)
    for sample in db.query(Sample).filter_by(campaign_id=c.id):
        if not db.query(Exposure.id).filter_by(user_id=actor,pair_key=sample.pair_key).first():db.add(Exposure(user_id=actor,pair_key=sample.pair_key))
    audit(db,actor,'close',c.id,report_version=r.version);db.flush();return r


def rank_change(before,after,relevance,universe_size):
    a=before if before is not None else universe_size+1
    b=after if after is not None else universe_size+1
    if a==b:return 'UNCHANGED'
    good=(b<a) if relevance>=2 else (b>a)
    return 'IMPROVES' if good else 'WORSENS'
