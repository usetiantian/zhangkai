"""E2E test: Phase 1-6 integration."""
import sys,os,time,json,shutil,threading,urllib.request
sys.path.insert(0, '.')

lake_dir = './_e2e_test_'
shutil.rmtree(lake_dir, ignore_errors=True)
os.makedirs(lake_dir, exist_ok=True)

# Phase 1-3
with open(os.path.join(lake_dir, 'semi.md'), 'w') as f: f.write('TSMC leads 3nm.')
with open(os.path.join(lake_dir, 'ai.txt'), 'w') as f: f.write('NVIDIA H100 GPU.')
with open(os.path.join(lake_dir, 'cfg.json'), 'w') as f: json.dump({'s':'m'}, f)
from docx import Document; d=Document(); d.add_paragraph('AMD GPU.'); d.save(os.path.join(lake_dir, 'rpt.docx'))
from nexus_kb import KnowledgeBase; kb=KnowledgeBase(lake_dir); kb.rescan()
assert kb.rag.stats()['docs']==4
print('[1] Ingest OK')

# Phase 4
from nexus_kb.api.server import serve
t=threading.Thread(target=serve, args=(kb,), kwargs={'port':18773}, daemon=True); t.start(); time.sleep(0.3)
def post(p, d):
    b=json.dumps(d).encode(); r=urllib.request.Request('http://127.0.0.1:18773'+p, b, {'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(r, timeout=3).read())
assert post('/search', {'q':'TSMC'})['results']
print('[2] API OK')
from nexus_kb.api.mcp import handle_request, set_kb; set_kb(kb)
r=handle_request({'method':'tools/list','id':1})
assert len(r['result']['tools'])==9
print('[3] MCP 9 tools OK')

# Phase 5
ts=kb.training_status(); assert ts['current_docs']==4 and ts['history']==0
print('[4] LoRA OK')

# Phase 6
from nexus_kb.learn.web import WebCrawler, WebKnowledgeBridge
c=WebCrawler(); html='<html><title>T</title><body><p>AI chips 800B.</p><script>x()</script></body></html>'
text=c._extract_text(html)
assert 'AI chips' in text and 'x()' not in text
print('[5] HTML extraction OK')
bridge=WebKnowledgeBridge(kb); bridge.kb.ingest_text('Web: AI chips 800B 2026.','web:test')
assert len(kb.search('800B'))>=1
print('[6] Web ingest OK')
r=kb.web_search('test'); assert isinstance(r, list)
print('[7] Web search graceful (empty)')

# Watcher
w=kb.watch()
fp=os.path.join(lake_dir, 'new.txt')
with open(fp, 'w') as f: f.write('UNIQ999 test.')
ev=w.run_once()
assert len(ev)==1 and ev[0]['type']=='added'
assert len(kb.search('UNIQ999'))==1
print('[8] Watcher add OK')
time.sleep(0.3)
with open(fp, 'w') as f: f.write('MOD888 test.')
ev=w.run_once()
assert len(kb.search('MOD888'))==1
print('[9] Watcher modify OK')
os.remove(fp); w.run_once()
assert not any('new.txt' in s['source'] for s in kb.search('MOD888'))
print('[10] Watcher delete OK')

# Persist
kb.save(); kb2=KnowledgeBase(lake_dir)
assert kb2.rag.stats()['docs']==kb.rag.stats()['docs']
for q in ['TSMC','GPU','800B']: assert len(kb2.search(q))>=1
print('[11] Persist OK')
print('[12] Community:', len(kb.detect_communities()))

shutil.rmtree(lake_dir, ignore_errors=True)
print('ALL PASSED')
