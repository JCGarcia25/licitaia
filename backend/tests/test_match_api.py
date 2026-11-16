"""Autorización, aislamiento y coherencia de consumidores de scores."""
from uuid import uuid4
from app.db.models import Company, CompanyProfile, MatchJob, Opportunity, User, UserOpportunity
from app.services.match_jobs import process_batch
from match_test_support import finish_job


def account(client):
    email = f'{uuid4().hex}@example.com'
    response = client.post('/api/auth/register', json={'email':email,'password':'ClaveSegura123','full_name':'Prueba'})
    assert response.status_code == 201
    return email, {'Authorization':f"Bearer {response.json()['access_token']}"}


def test_trabajos_privados_incluso_en_misma_empresa(client, db):
    accounts = [account(client) for _ in range(3)]
    users = [db.query(User).filter_by(email=email).one() for email, _ in accounts]
    company = Company(nombre='Empresa A', owner_user_id=users[0].id)
    other = Company(nombre='Empresa B', owner_user_id=users[2].id)
    db.add_all([company, other]); db.flush()
    users[0].company_id = users[1].company_id = company.id
    users[2].company_id = other.id
    db.commit()
    headers = accounts[0][1]
    assert client.put('/api/profile', headers=headers, json={'sector':'software','keywords':['software']}).status_code == 200
    response = client.post('/api/rescore', headers=headers, json={'user_id':users[2].id})
    assert response.status_code == 202
    jid = response.json()['id']
    assert db.get(MatchJob, jid).user_id == users[0].id
    assert db.query(UserOpportunity).filter_by(user_id=users[0].id).count() == 0
    assert client.post('/api/rescore', headers=headers).json()['id'] == jid
    for _, foreign in accounts[1:]:
        assert client.get(f'/api/match-jobs/{jid}', headers=foreign).status_code == 404
        assert client.post(f'/api/match-jobs/{jid}/cancel', headers=foreign).status_code == 404
        assert client.post(f'/api/match-jobs/{jid}/resume', headers=foreign).status_code == 404
        assert client.get('/api/match-jobs/current', headers=foreign).json() is None
    assert client.post('/api/rescore').status_code == 401
    assert client.get('/api/matches/coverage').status_code == 401
    assert client.post(f'/api/match-jobs/{jid}/cancel', headers=headers).json()['state'] == 'CANCELLED'
    assert process_batch(db, jid)['status'] == 'BUSY'
    resumed = client.post(f'/api/match-jobs/{jid}/resume', headers=headers)
    assert resumed.status_code == 202 and resumed.json()['id'] != jid


def test_score_obsoleto_oculto_en_busqueda_dashboard_y_alertas(client, db):
    email, headers = account(client)
    user = db.query(User).filter_by(email=email).one()
    marker = uuid4().hex
    opp = Opportunity(source='qa', source_id=marker, objeto=f'Software especializado {marker}',
        descripcion='software', estado='En proceso', departamento='Meta', valor=100)
    db.add(opp); db.commit()
    client.put('/api/profile', headers=headers, json={'sector':'software','actividades':'software',
        'keywords':['software'], 'departamentos':['Meta'], 'modalidades':[]})
    response = client.post('/api/rescore', headers=headers)
    finish_job(db, response.json()['id'])
    initial = client.get(f'/api/opportunities/{opp.id}', headers=headers).json()
    assert initial['score_state'] == 'CURRENT' and initial['score'] is not None
    original = db.query(UserOpportunity).filter_by(user_id=user.id, opportunity_id=opp.id).one().score
    client.post(f'/api/opportunities/{opp.id}/triaje', headers=headers, json={'triage':'guardada'})
    client.put('/api/profile', headers=headers, json={'sector':'agricultura','keywords':['semillas']})
    detail = client.get(f'/api/opportunities/{opp.id}', headers=headers).json()
    assert detail['score'] is None and detail['score_state'] == 'STALE' and detail['triage'] == 'guardada'
    filtered = client.get(f'/api/opportunities?score_min=0&q={marker}', headers=headers).json()
    assert filtered['total'] == 0
    search = client.post('/api/search', headers=headers, json={'q':marker,'solo_con_score':True}).json()
    assert search['total'] == 0
    assert client.get('/api/dashboard/metrics?compatibility_threshold=0', headers=headers).json()['alta_compatibilidad'] == 0
    assert all(a['opportunity_id'] != opp.id for a in client.get('/api/alerts', headers=headers).json())
    db.expire_all()
    saved = db.query(UserOpportunity).filter_by(user_id=user.id, opportunity_id=opp.id).one()
    assert saved.score == original and saved.triage == 'guardada'

def test_descartada_no_se_recomienda_en_alertas_ni_dashboard(client, db):
    email, headers = account(client)
    marker = uuid4().hex
    opp = Opportunity(source='qa', source_id=marker, objeto=f'software {marker}', estado='En proceso')
    db.add(opp); db.commit()
    client.put('/api/profile', headers=headers, json={'sector':'software','keywords':['software']})
    result = client.post('/api/rescore', headers=headers)
    finish_job(db, result.json()['id'])
    client.put('/api/alerts/prefs', headers=headers, json={'high_score_threshold':0})
    assert opp.id in {a['opportunity_id'] for a in client.get('/api/alerts', headers=headers).json()}
    before = client.get('/api/dashboard/metrics?compatibility_threshold=0', headers=headers).json()['alta_compatibilidad']
    client.post(f'/api/opportunities/{opp.id}/triaje', headers=headers, json={'triage':'descartada'})
    assert opp.id not in {a['opportunity_id'] for a in client.get('/api/alerts', headers=headers).json()}
    after = client.get('/api/dashboard/metrics?compatibility_threshold=0', headers=headers).json()['alta_compatibilidad']
    assert after == before - 1
    explicit = client.get(f'/api/opportunities?q={marker}&triage=descartada&score_min=0', headers=headers).json()
    assert opp.id in {o['id'] for o in explicit['items']}

def test_operational_metrics_private_and_all_matching_routes_authenticated(client,db):
    first,headers=account(client);second,foreign=account(client)
    u1=db.query(User).filter_by(email=first).one();u2=db.query(User).filter_by(email=second).one()
    client.put('/api/profile',headers=headers,json={'sector':'software'})
    client.put('/api/profile',headers=foreign,json={'sector':'salud'})
    job=db.query(MatchJob).filter_by(user_id=u2.id).one()
    job.state='FAILED';job.error='PrivateFailure';db.commit()
    result=client.get('/api/matches/metrics',headers=headers).json()
    assert result['failed_jobs']==0 and 'PrivateFailure' not in str(result)
    result=client.get('/api/matches/metrics',headers=foreign).json()
    assert result['failed_jobs']==1 and result['errors_by_component']['matching']=={'PrivateFailure':1}
    own=client.get('/api/match-jobs/current',headers=headers).json()
    assert 'profile_vector' not in own and 'profile' not in own
    for path in ['/api/matches/metrics','/api/matches/coverage','/api/match-jobs/current',f'/api/match-jobs/{job.id}']:
        assert client.get(path).status_code==401
    for path in ['/api/rescore',f'/api/match-jobs/{job.id}/cancel',f'/api/match-jobs/{job.id}/resume']:
        assert client.post(path).status_code==401
