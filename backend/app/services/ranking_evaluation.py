"""Evaluación offline; juicios independientes, sin entrenar ni alterar el matcher."""
from collections import defaultdict
from datetime import datetime
import math
from statistics import mean


def evaluate(predictions,judgments,queries,allow_synthetic=False):
    manifests={q['query_id']:q for q in queries}
    if len(manifests)!=len(queries):raise ValueError('query_id duplicado')
    labels={}; rankings=defaultdict(list); prediction_rows=defaultdict(list); sources=set()
    for row in judgments:
        if row.get('relevance') is None:continue
        key=(row['query_id'],row['opportunity_id'])
        if key in labels:raise ValueError('Juicio duplicado')
        if type(row['relevance']) is not int or row['relevance'] not in range(4):raise ValueError('Relevancia debe ser 0–3')
        source=row.get('label_source')
        if source!='human' and not (allow_synthetic and source=='synthetic_test'):raise ValueError('Se requieren etiquetas humanas independientes')
        if not row.get('blinded') or not row.get('reason') or not row.get('evaluator_id'):raise ValueError('Falta procedencia independiente del juicio')
        datetime.fromisoformat(row['evaluated_at'].replace('Z','+00:00'))
        if row['query_id'] not in manifests:raise ValueError('Juicio sin universo declarado')
        if row['opportunity_id'] not in manifests[row['query_id']]['universe_ids']:raise ValueError('Juicio fuera del universo')
        labels[key]=row;sources.add(source)
    seen=set()
    for row in predictions:
        key=(row['query_id'],row['opportunity_id'])
        if key in seen:raise ValueError('Predicción duplicada')
        seen.add(key)
        if row['query_id'] not in manifests or row['opportunity_id'] not in manifests[row['query_id']]['universe_ids']:
            raise ValueError('Predicción fuera del universo')
        prediction_rows[row['query_id']].append(row)
        if row.get('score') is None:continue
        if not math.isfinite(row['score']) or not 0<=row['score']<=100:raise ValueError('Score fuera del rango finito 0–100')
        if not all(row.get(k) for k in ('algorithm_version','profile_version','opportunity_version')):raise ValueError('Faltan versiones')
        label=labels.get(key)
        if label and any(label.get(k)!=row.get(k) for k in ('profile_version','opportunity_version')):raise ValueError('Juicio de entradas distintas')
        if row.get('eligible',True):rankings[row['query_id']].append(row)
    reports=[]
    for query in queries:
        qid=query['query_id'];universe=query['universe_ids']
        if len(set(universe))!=len(universe):raise ValueError('Universo duplicado')
        rows=rankings[qid]
        if any(r.get('rank') is not None for r in rows):
            ranks=[r.get('rank') for r in rows]
            if any(type(rank) is not int or rank<1 for rank in ranks) or len(set(ranks))!=len(ranks):
                raise ValueError('Ranks explícitos deben ser positivos y únicos')
            ranked=sorted(rows,key=lambda r:r['rank'])
        else:
            # Igual que el serving para IDs numéricos: score DESC, id DESC.
            if rows and all(str(r['opportunity_id']).isdigit() for r in rows):
                ranked=sorted(rows,key=lambda r:int(str(r['opportunity_id'])),reverse=True)
            else:
                ranked=sorted(rows,key=lambda r:str(r['opportunity_id']),reverse=True)
            ranked=sorted(ranked,key=lambda r:r['score'],reverse=True)
        versions={r['algorithm_version'] for r in ranked}
        if len(versions)>1:raise ValueError('No mezclar versiones de algoritmo en un ranking')
        if len({r['profile_version'] for r in ranked})>1:raise ValueError('No mezclar versiones de perfil en una consulta')
        labeled={oid:labels[(qid,oid)]['relevance'] for oid in universe if (qid,oid) in labels}
        complete=bool(query.get('universe_complete')) and len(labeled)==len(universe) and bool(universe)
        report={'query_id':qid,'sector':query.get('sector','unspecified'),'universe_total':len(universe),
            'labeled_total':len(labeled),'evaluation_coverage':len(labeled)/len(universe) if universe else None,
            'precision_at_5':None,'precision_at_10':None,'recall_at_20':None,'ndcg_at_10':None,'false_positive_rate':None}
        execution_complete=set(r['opportunity_id'] for r in prediction_rows[qid])==set(universe) and bool(universe) and all(r.get('computed') is True for r in prediction_rows[qid])
        if query.get('require_complete_execution') and not execution_complete:
            reports.append(report);continue
        if complete and query.get('ranking_complete') and execution_complete and not ranked:
            report['precision_at_5']=report['precision_at_10']=0.
            if any(value>=2 for value in labeled.values()):report['recall_at_20']=0.
            if any(labeled.values()):report['ndcg_at_10']=0.
        for k in (5,10):
            top=ranked[:k]
            if top and all(r['opportunity_id'] in labeled for r in top):
                report[f'precision_at_{k}']=sum(labeled[r['opportunity_id']]>=2 for r in top)/k
        relevant={oid for oid,value in labeled.items() if value>=2}
        ranking_complete=bool(query.get('ranking_complete'))
        if complete and ranking_complete and ranked and relevant:
            report['recall_at_20']=len(relevant & {r['opportunity_id'] for r in ranked[:20]})/len(relevant)
        if complete and ranking_complete and ranked:
            dcg=sum((2**labeled[r['opportunity_id']]-1)/math.log2(i+2) for i,r in enumerate(ranked[:10]))
            ideal=sum((2**label-1)/math.log2(i+2) for i,label in enumerate(sorted(labeled.values(),reverse=True)[:10]))
            report['ndcg_at_10']=dcg/ideal if ideal else None
            by_id={r['opportunity_id']:r for r in ranked}
            negatives={oid for oid,label in labeled.items() if label<2}
            if negatives and set(universe)<=set(by_id):
                threshold=query.get('positive_score_threshold',70)
                if not math.isfinite(threshold) or not 0<=threshold<=100:raise ValueError('Umbral positivo inválido')
                report['false_positive_rate']=sum(by_id[oid]['score']>=threshold for oid in negatives)/len(negatives)
        reports.append(report)
    metrics=('precision_at_5','precision_at_10','recall_at_20','ndcg_at_10','false_positive_rate','evaluation_coverage')
    def aggregate(rows):
        return {key:mean([r[key] for r in rows if r[key] is not None]) if any(r[key] is not None for r in rows) else None for key in metrics}
    sectors=defaultdict(list)
    for report in reports:sectors[report['sector']].append(report)
    return {'status':'MEASURED' if labels else 'PENDING_HUMAN_LABELS','label_sources':sorted(sources),
        'human_judgment_count':sum(r.get('label_source')=='human' for r in labels.values()),
        'metric_query_counts':{key:sum(r[key] is not None for r in reports) for key in metrics},
        'relevant_labels':[2,3],'ranking_order':'explicit rank if supplied; otherwise score DESC, id DESC (numeric when all numeric)','precision_denominator':'k; missing returned slots count as zero; unjudged results are not zero',
        'macro':aggregate(reports),'by_sector':{key:aggregate(rows) for key,rows in sectors.items()},'queries':reports,
        'warning':'El score heurístico no es probabilidad de adjudicación. Recall/NDCG/FPR exigen universo de referencia completo.'}
