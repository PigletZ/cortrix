"""核对当前 Archify 图源、HTML 与通过收据的 SHA-256 绑定。"""
from pathlib import Path
import hashlib,json,re
base=Path(__file__).resolve().parents[1]/'diagrams/archify'
root=base.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
errors=[]
for candidate in sorted(base.glob('*/candidate.json')):
    data=json.loads(candidate.read_text())
    output=root/data['meta']['output']
    name=candidate.parent.name
    if not output.exists():
        errors.append(f'{name}: HTML missing');continue
    spec_hash=sha(candidate);artifact_hash=sha(output)
    receipts=[]
    for p in candidate.parent.rglob('*.finalize-summary.json'):
        x=json.loads(p.read_text())
        if x.get('status')=='pass' and x.get('specification',{}).get('sha256')==spec_hash and x.get('artifact',{}).get('sha256')==artifact_hash and all(x.get('gates',{}).get(k)=='pass' for k in ['validate','deliver','check','browser-check']):receipts.append((p,x))
    if not receipts:
        errors.append(f'{name}: no passing receipt bound to current JSON and HTML');continue
    p,x=max(receipts,key=lambda v:v[0].stat().st_mtime_ns)
    records.append({'name':name,'title':data['meta']['title'],'status':'pass','gates':x['gates'],'candidate':str(candidate.relative_to(base)),'html':str(output.relative_to(base)),'receipt':str(p.relative_to(base)),'specification_sha256':spec_hash,'artifact_sha256':artifact_hash})
for dest in re.findall(r'href="([^"]+)"',(base/'index.html').read_text()):
    if not dest.startswith(('http:','https:','#')) and not (base/dest).exists():errors.append(f'gallery missing link: {dest}')
report={'status':'fail' if errors else 'pass','diagrams':records,'errors':errors,'scope':'Schema, source references, layout, artifact and automated browser gates; not Cortrix runtime verification.'}
(base/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if errors:raise SystemExit('\n'.join(errors))
print(f'PASS: {len(records)} current diagrams; JSON/HTML hashes match passing Archify receipts; gallery links valid.')
