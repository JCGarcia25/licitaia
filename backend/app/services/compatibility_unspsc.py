"""Verified catalog membership before comparing hierarchical numeric identifiers."""
import json
import re
from functools import lru_cache
from pathlib import Path
from app.services.match_versions import digest

@lru_cache
def catalog():
    return json.loads((Path(__file__).parent.parent / 'data/unspsc_v14_codes.json').read_text())

@lru_cache
def members():
    return frozenset(catalog()['codes'])


@lru_cache
def catalog_version():
    return digest(catalog())


def compare(company_codes, opportunity_code, weights=(1.0, .7, .4, .15)):
    valid = lambda v: isinstance(v, str) and bool(re.fullmatch(r'\d{8}', v)) and v in members()
    codes = sorted(set(c for c in company_codes if valid(c)))
    if not codes or not valid(opportunity_code):
        return {'score': None, 'relation': 'INSUFFICIENT', 'level': None, 'source': catalog()['source']}
    best = (0., 'NONE', None)
    for code in codes:
        # An aggregate class code is never an exact product match.
        for length, level, score in ((8,'PRODUCT',weights[0]),(6,'CLASS',weights[1]),(4,'FAMILY',weights[2]),(2,'SEGMENT',weights[3])):
            if code[:length] == opportunity_code[:length] and (length == 2 or (code[:length][-2:] != '00' and opportunity_code[:length][-2:] != '00')):
                if score > best[0]:
                    best = (score, 'EXACT' if length == 8 else 'HIERARCHICAL', level)
                break
    return {'score': best[0], 'relation': best[1], 'level': best[2], 'source': catalog()['source'], 'catalog_version': catalog_version()}
