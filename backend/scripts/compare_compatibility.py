"""python scripts/compare_compatibility.py legacy.jsonl v2.jsonl labels.jsonl queries.jsonl"""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.compatibility_evaluation import compare

def read(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
if __name__=='__main__':
    if len(sys.argv)!=5:raise SystemExit(__doc__)
    print(json.dumps(compare(*(read(p) for p in sys.argv[1:])),indent=2,ensure_ascii=False))
