import pytest
from app.services.ranking_evaluation import evaluate


def data():
    predictions=[{'query_id':'q','opportunity_id':str(i),'score':100-i*10,'algorithm_version':'v1','profile_version':'p','opportunity_version':str(i)} for i in range(6)]
    judgments=[{'query_id':'q','opportunity_id':str(i),'relevance':label,'label_source':'synthetic_test','blinded':True,'reason':'fixture matemático','evaluator_id':'test','evaluated_at':'2026-11-15T00:00:00Z','profile_version':'p','opportunity_version':str(i)} for i,label in enumerate([3,2,0,0,1,3])]
    queries=[{'query_id':'q','sector':'test','universe_ids':[str(i) for i in range(6)],'universe_complete':True,'ranking_complete':True,'positive_score_threshold':70}]
    return predictions,judgments,queries


def test_metrics_known_synthetic_not_human():
    p,j,q=data();r=evaluate(p,j,q,allow_synthetic=True)
    assert r['macro']['precision_at_5']==.4
    assert r['macro']['precision_at_10']==.3
    assert r['macro']['recall_at_20']==1
    assert r['macro']['false_positive_rate']==pytest.approx(2/3)
    assert 0<r['macro']['ndcg_at_10']<1
    with pytest.raises(ValueError):evaluate(p,j,q)


def test_partial_labels_never_assume_negatives_or_complete_recall():
    p,j,q=data();q[0]['universe_complete']=False
    r=evaluate(p,j[:2],q,allow_synthetic=True)
    assert all(r['macro'][k] is None for k in ('precision_at_5','precision_at_10','recall_at_20','ndcg_at_10','false_positive_rate'))
    assert r['macro']['evaluation_coverage']==pytest.approx(1/3)


def test_empty_labels_pending_and_versions_validated():
    p,j,q=data();r=evaluate(p,[],q)
    assert r['status']=='PENDING_HUMAN_LABELS' and r['macro']['precision_at_5'] is None
    j[0]['profile_version']='other'
    with pytest.raises(ValueError):evaluate(p,j,q,allow_synthetic=True)

def test_ties_match_serving_order_or_explicit_snapshot_rank():
    p,j,q=data()
    for r in p:r['score']=75
    r=evaluate(p,j,q,allow_synthetic=True)
    assert r['queries'][0]['precision_at_5']==.4  # IDs 5..1: relevantes 5,1
    default_ndcg=r['queries'][0]['ndcg_at_10']
    for i,row in enumerate(p):row['rank']=i+1
    r=evaluate(p,j,q,allow_synthetic=True)
    assert r['queries'][0]['precision_at_5']==.4  # IDs 0..4: relevantes 0,1
    assert r['queries'][0]['ndcg_at_10']>default_ndcg
    p[1]['rank']=p[0]['rank']
    with pytest.raises(ValueError):evaluate(p,j,q,allow_synthetic=True)
