from uuid import uuid4
from datetime import datetime,timedelta
import pytest
from app.db.models import User,Opportunity,UserOpportunity,Subscription

@pytest.fixture
def saved_setup(client,db,auth_headers):
    u=db.query(User).filter_by(email=client.get('/api/auth/me',headers=auth_headers).json()['email']).one()
    db.add(Subscription(user_id=u.id,plan='profesional',status='activa',provider='test'))
    word='sintetico'+uuid4().hex;rows=[]
    for i in range(3):
        o=Opportunity(source='qa',source_id=uuid4().hex,objeto=f'{word} {i}',estado='Publicado',fecha_publicacion=datetime.utcnow()-timedelta(days=1),cancelled=False)
        db.add(o);db.flush();rows.append(o)
    db.commit();return u,rows,word,auth_headers

def test_persistence_first_before_pagination_get_and_post(saved_setup,client,db):
    u,rows,q,h=saved_setup;oid=rows[0].id
    for _ in range(2):assert client.patch(f'/api/opportunities/{oid}/saved',headers=h,json={'saved':True}).status_code==200
    for r in [client.get(f'/api/opportunities?q={q}&limit=1',headers=h),client.post('/api/search',headers=h,json={'q':q,'limit':1})]:
        assert r.status_code==200,r.text
        assert r.json()['total']==3 and r.json()['items'][0]['id']==oid and r.json()['items'][0]['is_saved']
    assert db.query(UserOpportunity).filter_by(user_id=u.id,opportunity_id=oid).count()==1
    assert client.get(f'/api/opportunities?q={q}&triage=guardada',headers=h).json()['total']==1

def test_offer_does_not_erase_saved_and_unsave_does_not_erase_offer(saved_setup,client):
    u,rows,q,h=saved_setup;oid=rows[0].id
    assert client.patch(f'/api/opportunities/{oid}/saved',headers=h,json={'saved':True}).status_code==200
    p=client.post('/api/offer-projects',headers=h,json={'opportunity_id':oid});assert p.status_code==201,p.text
    d=client.get(f'/api/opportunities/{oid}',headers=h).json();assert d['is_saved'] and d['triage']=='proyecto'
    assert client.patch(f'/api/opportunities/{oid}/saved',headers=h,json={'saved':False}).status_code==200
    d=client.get(f'/api/opportunities/{oid}',headers=h).json();assert not d['is_saved'] and d['triage']=='proyecto'
    assert client.get(f'/api/offer-projects/{p.json()["id"]}',headers=h).status_code==200
    assert client.get(f'/api/opportunities?q={q}&triage=guardada',headers=h).json()['total']==0

def test_legacy_saved_and_user_isolation(saved_setup,client,db):
    u,rows,q,h=saved_setup;db.add(UserOpportunity(user_id=u.id,opportunity_id=rows[0].id,triage='guardada'));db.commit()
    assert client.get(f'/api/opportunities?q={q}&limit=1',headers=h).json()['items'][0]['is_saved']
    r=client.post('/api/auth/register',json={'email':uuid4().hex+'@example.com','password':'SyntheticPassword123','full_name':'QA'})
    other={'Authorization':'Bearer '+r.json()['access_token']};d=client.get(f'/api/opportunities?q={q}&limit=1',headers=other).json()['items'][0]
    assert d['id']==rows[-1].id and not d['is_saved']

def test_saved_respects_other_filters(saved_setup,client):
    u,rows,q,h=saved_setup;assert client.patch(f'/api/opportunities/{rows[0].id}/saved',headers=h,json={'saved':True}).status_code==200
    assert client.get(f'/api/opportunities?q={q}&departamento=Atlantico',headers=h).json()['total']==0

def test_preparador_lists_saved_first(saved_setup,client):
    u,rows,q,h=saved_setup
    first=client.post('/api/offer-projects',headers=h,json={'opportunity_id':rows[0].id}).json()['id']
    second=client.post('/api/offer-projects',headers=h,json={'opportunity_id':rows[1].id}).json()['id']
    assert client.patch(f'/api/opportunities/{rows[1].id}/saved',headers=h,json={'saved':False}).status_code==200
    projects=client.get('/api/offer-projects',headers=h).json()
    assert [p['id'] for p in projects]==[first,second]
    assert projects[0]['is_saved'] and not projects[1]['is_saved']

def test_can_opt_out_of_saved_priority_for_dashboard(saved_setup,client):
    u,rows,q,h=saved_setup
    assert client.patch(f'/api/opportunities/{rows[0].id}/saved',headers=h,json={'saved':True}).status_code==200
    result=client.get(f'/api/opportunities?q={q}&limit=1&prioritize_saved=false',headers=h).json()
    assert result['items'][0]['id']==rows[-1].id
