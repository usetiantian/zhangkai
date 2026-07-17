# -*- coding: utf-8 -*-
"""Fix knowledge_generator — use EvoKG's existing triple infrastructure."""
import py_compile
SRC = r"C:\Users\87999\.nexus\nexus_agent\knowledge_generator.py"

f = open(SRC, 'r', encoding='utf-8')
content = f.read()
f.close()

old_marker = '    def _try_extract_from_evokg(self, domain: str) -> List[Dict]:'
old_end_marker = '    def _try_extract_from_codebase(self, domain: str) -> List[Dict]:'

idx_start = content.find(old_marker)
idx_end = content.find(old_end_marker)
if idx_start < 0 or idx_end < 0:
    print('ERROR: markers')
    exit(1)

NL = chr(10)
new_method = f'''    def _try_extract_from_evokg(self, domain: str) -> List[Dict]:
        """v20: 三元组→EvoKG图边。使用已有的RelationType+add_edge基础设施。"""
        results=[]
        try:
            from nexus_agent.evokg import get_evokg, RelationType, SubgraphType
            kg=get_evokg()
            kw_map={{"programming":"python","math":"algorithm","ai":"learning",
                    "finance":"stock","tcm":"人参"}}
            nodes=kg.query_nodes(keyword=kw_map.get(domain,domain), limit=50)
            for node in nodes:
                raw=getattr(node,'content','') or str(node)[:800]
                raw_str=str(raw)
                if len(raw_str)<80: continue
                node_id=getattr(node,'id','') or ''
                
                # Extract triples and store as real graph edges
                triples=self._extract_triples(raw_str, domain)
                edge_count=0
                for subj, pred, obj in triples:
                    rel=self._verb_to_relation(pred)
                    if rel is None: continue
                    try:
                        subj_id=f"kg_{{hash(subj)%99999}}"
                        obj_id=f"kg_{{hash(obj)%99999}}"
                        # Ensure nodes exist
                        if not kg.get_node(subj_id):
                            kg.add_node(SubgraphType.DOMAIN_KNOWLEDGE,subj,subj_id,0.5)
                        if not kg.get_node(obj_id):
                            kg.add_node(SubgraphType.DOMAIN_KNOWLEDGE,obj,obj_id,0.5)
                        kg.add_edge(subj_id,obj_id,rel,0.5,None,domain)
                        edge_count+=1
                    except Exception:
                        pass
                
                if edge_count>0:
                    name=f"kg_{{getattr(node,'id','')[:12]}}"
                    triples_text=NL.join(f"  {{s}} --{{p}}--> {{o}}" for s,p,o in triples[:5])
                    code=f"# Triples from: {{raw_str[:80]}}...{NL}{{triples_text}}"
                    results.append({{"name":name,"code":code[:600],"domain":domain,
                        "meta":{{"edges_created":edge_count,"triples_found":len(triples)}}}})
            if results:
                logger.info("[KnowledgeGen] %s: 三元组→%d图边", domain, 
                    sum(r.get("meta",{{}}).get("edges_created",0) for r in results))
        except Exception:
            logger.debug("EvoKG extract failed", exc_info=True)
        return results

    def _verb_to_relation(self, verb: str):
        """Map extracted verb to EvoKG RelationType."""
        from nexus_agent.evokg import RelationType
        mapping={{
            'is_a':RelationType.CONTAINS,
            'has_property':RelationType.CONTAINS,
            'uses':RelationType.USES,
            'uses_method':RelationType.USES,
            'enables':RelationType.ENABLES,
            'improves':RelationType.IMPROVES,
            'reduces':RelationType.IMPROVES,
            'requires':RelationType.DEPENDS_ON,
            'supports':RelationType.ENABLES,
            'achieves':RelationType.PRODUCES,
            'creates':RelationType.PRODUCES,
            'generates':RelationType.PRODUCES,
            'trains':RelationType.IMPROVES,
            'optimizes':RelationType.IMPROVES,
            'detects':RelationType.ENABLES,
            'predicts':RelationType.ENABLES,
            'provides':RelationType.PRODUCES,
            'learns':RelationType.IMPROVES,
            'processes':RelationType.USES,
        }}
        return mapping.get(verb)

'''
content = content[:idx_start] + new_method + content[idx_end:]
f = open(SRC, 'w', encoding='utf-8')
f.write(content)
f.close()

py_compile.compile(SRC, doraise=True)
print('[OK] Uses EvoKG RelationType + add_edge for real graph triples')
