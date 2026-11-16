# Protocolo de evaluación independiente

No hay etiquetas humanas en estas plantillas. Las métricas reales están pendientes.

1. Definir consultas/perfiles anonimizados y un universo elegible completo, con referencia pública o texto anonimizado y fecha de snapshot. No exportar perfiles reales sin autorización. Conservar identificadores pseudónimos y hashes de las entradas.
2. Entregar `judgments.blind.template.jsonl` al evaluador sin predictions ni scores. Completar relevancia 0=irrelevante, 1=relación débil, 2=compatible con reservas, 3=altamente relevante, motivo, identificador pseudónimo y fecha ISO. Adjuntar estado/vigencia de la referencia. No inferir juicios desde feedback binario, score, clics o triage.
3. Registrar las predicciones del matcher sin alterar su fórmula, con versiones del algoritmo y de ambas entradas. Incluir rank para preservar exactamente el orden servido, sobre todo con referencias públicas que no sean IDs internos. Sin rank se usa score descendente e ID descendente, numérico cuando todos lo son. Mantenerlas separadas hasta terminar los juicios. Cada ejecución evalúa una única versión de algoritmo por consulta.
4. Relevantes son 2 y 3. Precision@k usa denominador k; listas cortas no reciben crédito por plazas vacías y resultados sin juicio producen null. No asumir que ausencia de etiqueta significa irrelevante.
5. Marcar universe_complete solo si el snapshot declara todo el universo de referencia y todos sus registros tienen juicios. Declarar también ranking_complete solo si el archivo contiene el ranking completo de esa ejecución. Recall@20, NDCG@10 y FPR no se publican como medidas completas en universos parciales. FPR = FP/(FP+TN), positivo = score >= umbral previamente definido; exige scores de todo el universo. La cobertura de evaluación es fracción del universo etiquetada. Agregados por sector y globales son macro promedios de consultas con métrica disponible; revisar cuántas consultas contribuyen, visibles en el detalle.
6. Repetir una muestra a ciegas con varios evaluadores, resolver desacuerdos sin consultar scores y mantener auditoría de motivos. Versionar cambios de juicios y universos; no mezclar versiones de entradas.

Desde backend:

```bash
.venv/bin/python scripts/evaluate_ranking.py evaluation/predictions.template.jsonl evaluation/judgments.blind.template.jsonl evaluation/queries.template.jsonl
```

Los casos unitarios usan etiquetas `synthetic_test` únicamente para verificar fórmulas; el CLI no las acepta como humanas. El score heurístico no representa probabilidad de ganar una adjudicación. No se entrena ningún modelo.
