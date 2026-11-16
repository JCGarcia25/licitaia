"""python scripts/evaluate_ranking.py predictions.jsonl judgments.jsonl queries.jsonl"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.ranking_evaluation import evaluate


def read(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('predictions','judgments','queries'):parser.add_argument(name)
    parser.add_argument('--output')
    args=parser.parse_args()
    result=evaluate(read(args.predictions),read(args.judgments),read(args.queries))
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    if args.output:Path(args.output).write_text(text+'\n')
    else:print(text)
