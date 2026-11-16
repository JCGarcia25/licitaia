"""Seeded bounded sampling; score strata never imply human relevance labels."""
from collections import defaultdict
import random
from app.services.match_versions import digest


def band(value, cuts):
    if value is None:return 'UNKNOWN'
    return str(sum(value>=cut for cut in cuts))


def stratum(row):
    o=row['opportunity'];b=row['predictions']['B']
    return {'sector':row['profile'].get('sector') or 'UNKNOWN','modality':o.get('modalidad') or 'UNKNOWN','amount':band(o.get('valor'),(100_000_000,1_000_000_000)), 'department':o.get('departamento') or 'UNKNOWN','validity':row.get('validity','UNKNOWN'),'legacy_level':band(row['predictions']['A'].get('score'),(40,70)),'v2_level':band(b.get('score'),(40,70)),'evidence':band(b.get('evidence_coverage'),(25,65)),'documents':bool(row.get('document_available',row.get('requirements'))),'retrieval_membership':row.get('retrieval_membership','UNAVAILABLE')}


def select(universe, size, seed, holdout_fraction=.2):
    if not universe or not 1<=size<=200 or not 0<=holdout_fraction<1:raise ValueError('Invalid bounded sampling request')
    if len({r['pair_key'] for r in universe})!=len(universe):raise ValueError('Duplicate input pair')
    # One deterministic representative per public procurement process globally.
    # The resulting frame, not all submitted duplicates, is the target universe.
    processes=defaultdict(list)
    for row in universe:processes[row['process_key']].append(row)
    frame=[];duplicates=[]
    for process,rows in sorted(processes.items()):
        rows=sorted(rows,key=lambda r:digest([seed,r['pair_key']]))
        frame.append(rows[0]);duplicates.extend(r['pair_key'] for r in rows[1:])
    # Actual frozen top-20 sets, not caller-supplied claims of model exclusivity.
    top={model:set() for model in ('A','B')}
    queries=defaultdict(list)
    for row in frame:queries[row['query_id']].append(row)
    for rows in queries.values():
        for model in ('A','B'):
            ranked=sorted((r for r in rows if r['predictions'][model].get('score') is not None),key=lambda r:(r['predictions'][model]['score'],r['pair_key']),reverse=True)
            top[model].update(r['pair_key'] for r in ranked[:20])
    frame=[dict(row) for row in frame]
    primary=defaultdict(list)
    for row in frame:
        a,b=row['predictions']['A'],row['predictions']['B']
        if a.get('score') is None or (b.get('score') is None and not b.get('result')):membership='UNCOMPUTED_REFERENCE'
        else:
            inside=(row['pair_key'] in top['A'],row['pair_key'] in top['B'])
            membership={(True,True):'BOTH',(True,False):'A_ONLY',(False,True):'B_ONLY',(False,False):'NEITHER'}[inside]
        row['retrieval_membership']=membership
        group=('INDEPENDENT/' if row.get('retrieval_origin')=='independent_search' else 'FRAME/')+membership
        primary[group].append(row)
    rng=random.Random(seed);n=min(size,len(frame));selected=[]
    def allocate(capacities,budget):
        keys=sorted(capacities);rng.shuffle(keys);result={k:0 for k in keys}
        if budget<len(keys):
            for k in keys[:budget]:result[k]=1
            return result,budget/len(keys)
        remaining=budget
        while remaining:
            for k in keys:
                if result[k]<capacities[k]:result[k]+=1;remaining-=1
                if not remaining:break
        return result,1.
    primary_allocation,primary_probability=allocate({k:len(v) for k,v in primary.items()},n)
    strata_count=0;selected_groups=defaultdict(int)
    for group in sorted(primary):
        rows=primary[group];groups=defaultdict(list)
        for row in sorted(rows,key=lambda r:r['pair_key']):groups[digest(stratum(row))].append(row)
        strata_count+=len(groups);budget=primary_allocation[group]
        if not budget:continue
        allocation,stratum_probability=allocate({k:len(v) for k,v in groups.items()},budget)
        for key in sorted(groups):
            for row in rng.sample(groups[key],allocation[key]):
                selected.append({'pair_key':row['pair_key'],'stratum':stratum(row),'retrieval_group':group,'inclusion_probability':primary_probability*stratum_probability*allocation[key]/len(groups[key]),'split':'development'})
                selected_groups[group]+=1
    # Reserve whole companies to holdout: no company appears in both partitions.
    company={r['pair_key']:r['company_cluster_id'] for r in frame}
    clusters=sorted({company[r['pair_key']] for r in selected});rng.shuffle(clusters)
    count=max(1,round(len(clusters)*holdout_fraction)) if len(clusters)>1 and holdout_fraction else 0
    reserved=set(clusters[:count])
    for row in selected:
        if company[row['pair_key']] in reserved:row['split']='holdout'
    return {'seed':seed,'requested':size,'selected':sorted(selected,key=lambda r:r['pair_key']),'submitted_pairs':len(universe),'frame_pairs':len(frame),'frame_keys':sorted(r['pair_key'] for r in frame),'duplicate_process_pairs_excluded':sorted(duplicates),'strata':strata_count,'retrieval_groups_available':{k:len(v) for k,v in primary.items()},'retrieval_groups_selected':dict(selected_groups),'probability_scope':'Conditional on recorded primary/fine-stratum allocation; excluded process duplicates are outside the frame','holdout_clusters':sorted(reserved),'warning':'Design probabilities refer only to the declared deduplicated frame. Unweighted ranking metrics are not population estimates. No labels inferred from strata.'}
