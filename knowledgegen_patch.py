    def _try_extract_external(self, domain: str) -> List[Dict]:
        """v18.5n: 外部真实数据源。finance=akshare, math=Python库, tcm=百度百科。"""
        results=[]
        try:
            if domain=="finance":
                try:
                    import akshare as ak
                    df=ak.stock_zh_a_spot_em()
                    if df is not None and len(df)>0:
                        sample=df.head(3).to_string()
                        results.append({"name":"akshare_stock","code":f"# akshare: {sample[:500]}","domain":domain,"meta":{"source":"akshare"}})
                except Exception:
                    logger.debug("akshare failed", exc_info=True)
            elif domain=="math":
                results.append({"name":"python_math","code":"import math,statistics,itertools,fractions,decimal,random\n# Python内置数学模块集","domain":domain,"meta":{"source":"python_stdlib"}})
            elif domain=="tcm":
                try:
                    import urllib.request,re
                    req=urllib.request.Request("https://baike.baidu.com/item/%E4%B8%AD%E5%8C%BB",headers={"User-Agent":"Nexus/1.0"})
                    with urllib.request.urlopen(req,timeout=8) as r:
                        html=r.read().decode("utf-8",errors="replace")
                        text=re.sub(r"<[^>]+>"," ",html)[:2000]
                        if len(text)>50:
                            results.append({"name":"baike_tcm","code":f"# 百度百科: {text[:500]}","domain":domain,"meta":{"source":"baidu_baike"}})
                except Exception:
                    logger.debug("baike failed", exc_info=True)
            if results:
                logger.info("[KnowledgeGen] %s: 外部源 %d条",domain,len(results))
        except Exception:
            logger.debug("External extract failed", exc_info=True)
        return results
