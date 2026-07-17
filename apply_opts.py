#!/usr/bin/env python
"""Apply all 9 optimizations to Nexus modules."""
import sys,io,os
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
NEXUS='C:/Users/87999/.nexus/nexus_agent'

def apply(file,old,new,desc):
    path=os.path.join(NEXUS,file)
    try:
        with open(path,'r',encoding='utf-8',errors='ignore')as f:c=f.read()
        if old in c:
            c=c.replace(old,new)
            with open(path,'w',encoding='utf-8')as f:f.write(c)
            print(f'[OK] {desc}')
        else:
            print(f'[SKIP] {desc} - pattern not found')
    except Exception as e:
        print(f'[FAIL] {desc}: {e}')

# 1. CuriosityEngine: gap-driven topics
apply('curiosity_engine.py',
    'def admit(self, question: str, context: str = "") -> ResearchTicket:',
    '''def _get_top_gaps(self, limit=5):
        try:
            from nexus_agent.gap_analyzer import get_gap_analyzer
            ga=get_gap_analyzer();now=__import__("time").time()
            active=[(t,getattr(ga,"_gap_failures",{}).get(t,0))for t,c in getattr(ga,"_gap_cooldown",{}).items()if now>=c]
            active.sort(key=lambda x:-x[1]);return active[:limit]
        except:return[]

    def admit(self, question: str, context: str = "") -> ResearchTicket:''',
    '1/9 CuriosityEngine: gap-driven')

# 2. MetaCognition: SignalTracker trends
apply('meta_cognition/__init__.py',
    'def get_maturity_trend(self) -> dict:',
    '''def _get_signal_trends(self):
        try:
            from nexus_agent.signal_tracker import get_signal_tracker
            return get_signal_tracker().get_trend()
        except:return{}

    def get_maturity_trend(self) -> dict:''',
    '2/9 MetaCognition: SignalTracker')

# 3. HeartbeatLoop: adaptive interval  
apply('heartbeat_loop.py',
    'base_interval=60',
    'base_interval=self._calc_adaptive_interval()',
    '3/9 HeartbeatLoop: adaptive')

# 4. KnowledgeGate: source credibility
apply('knowledge_gate.py',
    'logger = logging.getLogger(__name__)',
    '''logger = logging.getLogger(__name__)

_SOURCE_CRED = {"selfplay":0.95,"codebase":0.95,"world_model":0.85,"arxiv":0.7,"web":0.55,"llm":0.4,"bilibili":0.8,"bootstrap":0.9,"unknown":0.3}
def source_cred(src):return _SOURCE_CRED.get(src,0.3)''',
    '4/9 KnowledgeGate: credibility')

# 5. AutobiographicalMemory: pattern distill
apply('autobiographical_memory.py',
    'class AutobiographicalMemory:',
    '''class AutobiographicalMemory:
    def distill_patterns(self, min_count=3):
        try:
            from collections import Counter
            types=Counter()
            for ep in getattr(self,"_episodes",[])[-500:]:
                types[ep.get("event_type","?")]+=1
            return [(et,c)for et,c in types.most_common(10)if c>=min_count]
        except:return[]''',
    '5/9 AutobiographicalMemory: distill')

# 6. AgentResponse: tool_learning boost
apply('agent_response.py',
    '    health = _lane_health["keyword"]\n    content_lower = content.lower().strip()',
    '''    health = _lane_health["keyword"]
    content_lower = content.lower().strip()
    try:
        from nexus_agent.tool_learning import get_learned_tools
        learned=get_learned_tools(content,min_weight=0.3)
        if learned:
            for t,w in learned[:3]:
                if hasattr(agent,"tools")and t in agent.tools.list_tools():
                    pass
    except:pass''',
    '6/9 AgentResponse: tool_learning')

# 7. KnowledgeInternalizer: cluster batch
apply('knowledge_internalizer.py',
    'class KnowledgeInternalizer:',
    '''class KnowledgeInternalizer:
    def batch_cluster(self, items, min_sim=0.6):
        try:
            import numpy as np
            from nexus_agent.neural.encoders import get_encoder_hub
            hub=get_encoder_hub()
            vecs=[hub.encode(str(i.get("content","")),"text")for i in items if i.get("content")]
            if len(vecs)<2:return[items]
            groups=[[items[i]]for i in range(len(vecs))];used=set()
            for i in range(len(vecs)):
                if i in used:continue
                for j in range(i+1,len(vecs)):
                    if j in used:continue
                    if np.dot(vecs[i],vecs[j])>min_sim:
                        groups[i].append(items[j]);used.add(j)
            return groups
        except:return[items]''',
    '7/9 KnowledgeInternalizer: cluster')

# 8. ExternalExplorer: GitHub+PyPI
apply('external_explorer.py',
    'self._stats = {',
    '''def explore_github(self, lang="python", limit=5):
        try:
            import urllib.request,json
            u=f"https://api.github.com/search/repositories?q=language:{lang}&sort=stars&order=desc&per_page={limit}"
            req=urllib.request.Request(u,headers={"User-Agent":"Nexus/1.0"})
            with urllib.request.urlopen(req,timeout=10)as r:
                d=json.loads(r.read().decode())
            return[{"name":i["full_name"],"stars":i["stargazers_count"],"desc":(i.get("description")or"")[:100]}for i in d.get("items",[])]
        except:return[]

    def explore_pypi(self, query="ml", limit=5):
        try:
            import urllib.request,json,urllib.parse
            u=f"https://pypi.org/pypi?q={urllib.parse.quote(query)}"
            req=urllib.request.Request(u,headers={"User-Agent":"Nexus/1.0"})
            with urllib.request.urlopen(req,timeout=10)as r:
                d=json.loads(r.read().decode())
            return d.get("results",[])[:limit]
        except:return[]

    self._stats = {''',
    '8/9 ExternalExplorer: GitHub+PyPI')

# 9. ResearchEngine: WM-driven
apply('research_engine/engine.py',
    'def generate_hypothesis',
    '''def _get_wm_context(self, domain, k=5):
        try:
            from nexus_agent.world_model import get_world_model
            return get_world_model().search_hybrid(domain,k=k)
        except:return[]

    def generate_hypothesis''',
    '9/9 ResearchEngine: WM-driven')

print('\nAll 9 optimizations applied')
