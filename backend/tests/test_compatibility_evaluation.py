from copy import deepcopy
import pytest
from app.services.compatibility_evaluation import compare


def sample(queries=1,labels=False):
    a=[];b=[];js=[];qs=[]
    for q in range(queries):
        qid=str(q);qs.append({'query_id':qid,'company_cluster_id':qid,'sector':'test','snapshot_at':'2026-11-15T00:00:00Z','universe_ids':list(range(5)),'universe_complete':True,'ranking_complete':True})
        for i in range(5):
            row={'query_id':qid,'opportunity_id':i,'score':float(i*20),'algorithm_version':'legacy','profile_version':f'p{q}','opportunity_version':f'o{i}','snapshot_at':qs[-1]['snapshot_at']}
            a.append(row);b.append({**row,'algorithm_version':'v2','evidence_coverage':40.})
            if labels:js.append({'query_id':qid,'opportunity_id':i,'relevance':i%4,'profile_version':f'p{q}','opportunity_version':f'o{i}','label_source':'human','blinded':True,'reason':'TEST FIXTURE ONLY, not human collected','evaluator_id':'test','evaluated_at':qs[-1]['snapshot_at']})
    return a,b,js,qs


def test_no_labels_no_superiority():
    r=compare(*sample())
    assert r['status']=='PENDING_SUFFICIENT_HUMAN_LABELS' and not r['promotion_authorized']
    assert r['paired_deltas']['precision_at_10']['ci95'] is None
    assert r['non_evaluable_rate']==0


def test_unpaired_versions_windows_and_pairs_rejected():
    for field in ('profile_version','opportunity_version','snapshot_at'):
        a,b,j,q=sample();b[0][field]='changed'
        with pytest.raises(ValueError):compare(a,b,j,q)
    a,b,j,q=sample()
    with pytest.raises(ValueError):compare(a,b[:-1],j,q)
    j=[{'query_id':'0','opportunity_id':0,'relevance':3,'label_source':'synthetic_test'}]
    with pytest.raises(ValueError):compare(a,b,j,q)


def test_bootstrap_reproducible_algorithm_fixture_not_real_human_evidence():
    # Fake metadata exercises statistical code; never exported as evaluation evidence.
    args=sample(20,True)
    a=compare(*args);b=compare(*args)
    assert a==b and a['paired_deltas']['precision_at_10']['ci95']==[0.,0.]
    args=sample(19,True)
    assert compare(*args)['paired_deltas']['precision_at_10']['ci95'] is None


def test_abstention_and_missing_evidence_reported():
    a,b,j,q=sample();b[0]['score']=None;b[0]['evidence_coverage']=None
    r=compare(a,b,j,q)
    assert r['non_evaluable_rate']==.2 and r['mean_evidence_coverage']==40
