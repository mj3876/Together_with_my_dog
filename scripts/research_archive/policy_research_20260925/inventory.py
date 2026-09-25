import csv
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

root = Path.cwd()
files = []
for folder in ['data', 'runs', 'outputs']:
    for path in sorted((root / folder).rglob('*')):
        if not path.is_file() or path.name.startswith('~$'):
            continue
        item = dict(path=path.relative_to(root).as_posix(), bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if path.suffix.lower() == '.csv':
            for enc in ['utf-8-sig', 'cp949']:
                try:
                    with path.open(encoding=enc, newline='') as f:
                        rows = list(csv.reader(f))
                    item.update(encoding=enc, rows_excluding_first=max(0, len(rows)-1), first_row=rows[0] if rows else [])
                    break
                except UnicodeError:
                    continue
        if path.name in ['manifest.json','source_audit.json','pet_supply_audit.json']:
            try:
                d=json.loads(path.read_text(encoding='utf-8-sig'))
                item['audit_summary']={k:d[k] for k in ['status','start','end','total_places','counts','warnings','can_run_selection'] if k in d}
            except (ValueError, UnicodeError):
                pass
        files.append(item)
db = sqlite3.connect((root/'data/app.db').as_uri()+'?mode=ro',uri=True)
db_summary=[]
for name, sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"):
    quoted='"'+name.replace('"','""')+'"'
    db_summary.append(dict(table=name,ddl=sql,rows=db.execute('SELECT count(*) FROM '+quoted).fetchone()[0]))
db.close()
out=dict(scope='workspace data/runs/outputs only; no secrets; tmp research separately documented',files=files,existing_db=db_summary)
Path('tmp/policy_research_20260925/inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('file_count',len(files))
print('extensions',dict(Counter(Path(x['path']).suffix for x in files)))
for x in files:
    if 'rows_excluding_first' in x or 'audit_summary' in x:
        print(json.dumps({k:v for k,v in x.items() if k not in ['sha256','bytes']},ensure_ascii=False))
print('database',db_summary)
