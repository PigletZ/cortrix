"""使用项目本地 Archify 重绘 JSON 图源；结果收据保存在每张图旁。"""
from pathlib import Path
import json,os,subprocess,sys
root=Path(__file__).resolve().parents[2]
node=root/'.tools/node-v22.16.0-linux-x64/bin/node'
cli=root/'.tools/archify/bin/archify.mjs'
env=dict(os.environ,ARCHIFY_CHROME=str(root/'.tools/chrome/chrome-headless-shell-linux64/chrome-headless-shell'),ARCHIFY_CHROME_NO_SANDBOX='1')
results=[]
for p in sorted((root/'mydocs/diagrams/archify').glob('*/candidate.json')):
 if len(sys.argv)>1 and p.parent.name not in sys.argv[1:]:continue
 d=json.loads(p.read_text()); target=root/d['meta']['output']
 args=[str(node),str(cli),'finalize',d['diagram_type'],str(p),str(target),'--repo-root',str(root),'--quality','showcase','--json']
 if (target.parent/(target.stem+'.browser-check.json')).exists():
  i=2
  while (p.parent/f'review-{i}').exists():i+=1
  args+=['--out-dir',str(p.parent/f'review-{i}')]
 r=subprocess.run(args,cwd=root,env=env,text=True,capture_output=True)
 try:x=json.loads(r.stdout)
 except ValueError:x={'status':'error','diagnostics':[{'message':r.stderr or r.stdout}]}
 results.append({'name':p.parent.name,'status':x.get('status'),'gates':x.get('gates'),'diagnostics':x.get('diagnostics'), 'recommendation':x.get('visualReviewRecommendation')})
 print(json.dumps(results[-1],ensure_ascii=False),flush=True)
(root/'mydocs/diagrams/archify/latest-run.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')

if any(r["status"] != "pass" for r in results):
    raise SystemExit(1)
