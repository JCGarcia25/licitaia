"""Offline: python scripts/build_unspsc_catalog.py official.xls output.json (xlrd QA-only).
Stores numeric identifiers only; does not redistribute CCE's translated descriptions.
"""
import hashlib
import json
import sys
from pathlib import Path
import xlrd

source = Path(sys.argv[1])
sheet = xlrd.open_workbook(str(source)).sheet_by_index(0)
codes = set()
for row in range(4, sheet.nrows):
    for col, padding in ((0, 6), (2, 4), (4, 2), (6, 0)):
        value = sheet.cell_value(row, col)
        if isinstance(value, (int, float)) and value == int(value):
            code = str(int(value)) + '0' * padding
            if len(code) == 8:
                codes.add(code)
Path(sys.argv[2]).write_text(json.dumps({
    'version': 'UNSPSC-v14-CCE-numeric-identifiers',
    'source': 'https://operaciones.colombiacompra.gov.co/sites/cce_public/files/cce_clasificador/clasificador_de_bienes_y_servicios_v14_1.xls',
    'retrieved_at': '2026-11-15', 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'scope': 'Numeric membership only; translated descriptions not redistributed. Newer codes outside v14 are UNKNOWN.',
    'codes': sorted(codes)}, separators=(',', ':')) + '\n')
print(len(codes))
