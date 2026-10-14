"""离线检查文档链接、代码围栏与 Archify 图源和产物配对。"""
from pathlib import Path
import json
import re

base = Path(__file__).resolve().parents[1]
errors = []
markdown = sorted(base.rglob('*.md'))
for path in markdown:
    text = path.read_text(encoding='utf-8')
    if len(re.findall(r'^```', text, re.M)) % 2:
        errors.append(f'{path}: unclosed code fence')
    for dest in re.findall(r'\]\(([^)]+)\)', text):
        if '://' in dest or dest.startswith('#'):
            continue
        local = dest.split('#')[0]
        if local and not (path.parent / local).exists():
            errors.append(f'{path}: missing link {dest}')
diagrams = sorted((base / 'diagrams/archify').glob('*/candidate.json'))
if not diagrams:
    errors.append('Archify diagram sources are missing')
for diagram in diagrams:
    data = json.loads(diagram.read_text(encoding='utf-8'))
    output = base.parent / data['meta']['output']
    if not output.is_file():
        errors.append(f'{diagram}: missing HTML {output}')
for name in ['README.md', 'reference/evidence.md', 'reference/source-inventory.md', 'reference/api-inventory.md', 'diagrams/archify/README.md', 'diagrams/archify/index.html']:
    if not (base / name).exists():
        errors.append(f'missing {name}')
api = (base / 'reference/api-inventory.md').read_text(encoding='utf-8')
operations = len(re.findall(r'^\| \[', api, re.M))
if not operations:
    errors.append('API index is empty')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'PASS: {len(markdown)} Markdown files, {len(diagrams)} Archify source/HTML pairs, {operations} API operations; local links valid.')
