"""离线检查文档完整性；仅检查图源同步，不声称完成 Mermaid 语法渲染。"""
from pathlib import Path
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
gallery = (base / 'diagrams/README.md').read_text(encoding='utf-8')
for diagram in sorted((base / 'diagrams').glob('*.mmd')):
    source = diagram.read_text(encoding='utf-8').strip()
    if f'```mermaid\n{source}\n```' not in gallery:
        errors.append(f'{diagram}: gallery is not synchronized')
    if not source.startswith(('flowchart ', 'sequenceDiagram')):
        errors.append(f'{diagram}: unexpected diagram type')
for name in ['README.md', 'reference/evidence.md', 'reference/source-inventory.md', 'reference/api-inventory.md']:
    if not (base / name).exists():
        errors.append(f'missing {name}')
api = (base / 'reference/api-inventory.md').read_text(encoding='utf-8')
operations = len(re.findall(r'^\| \[', api, re.M))
if not operations:
    errors.append('API index is empty')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'PASS: {len(markdown)} Markdown files, {len(list((base / "diagrams").glob("*.mmd")))} synchronized diagrams, {operations} API operations; local links valid.')
