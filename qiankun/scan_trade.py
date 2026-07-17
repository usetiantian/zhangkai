#!/usr/bin/env python3
"""乾坤模拟交易 — 快速版：扫描前500只 + Qwen3-VL-4B分析 + 模拟买入"""
import sys,io,os,json,base64,urllib.request
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates
import baostock as bs, pandas as pd, numpy as np
from datetime import datetime,timedelta
from pathlib import Path

PORTFOLIO_FILE=Path(r'C:\Users\87999\claude-workspace\qiankun\portfolio.json')
CHARTS_DIR=Path(r'C:\Users\87999\claude-workspace\qiankun\charts')
CHARTS_DIR.mkdir(exist_ok=True)

pf={'cash':1000000,'positions':[],'history':[]}
if PORTFOLIO_FILE.exists():
    with open(PORTFOLIO_FILE,encoding='utf-8') as f: pf=json.load(f)

bs.login(); rs=bs.query_stock_basic(code_name=''); stocks=[]
while rs.next(): stocks.append(rs.get_row_data()); bs.logout()
df=pd.DataFrame(stocks,columns=['code','code_name','ipoDate','outDate','type','status'])
a_stocks=df[(df['type']=='1')&(df['status']=='1')]
codes=a_stocks['code'].tolist()
names=dict(zip(a_stocks['code'],a_stocks['code_name']))
print(f'{len(codes)} 只A股，扫前300只')

end=datetime.now().strftime('%Y-%m-%d')
start=(datetime.now()-timedelta(days=60)).strftime('%Y-%m-%d')
candidates=[]

for i in range(0,300,15):
    batch=codes[i:i+15]
    try:
        bs.login()
        for code in batch:
            try:
                rs=bs.query_history_k_data_plus(code,'date,close,volume',start_date=start,end_date=end,frequency='d',adjustflag='2')
                rows=[]; 
                while rs.next(): rows.append(rs.get_row_data())
                if len(rows)<30: continue
                closes=[float(r[1]) for r in rows[-30:]]
                volumes=[float(r[2]) for r in rows[-5:]]
                avg_vol=np.mean([float(r[2]) for r in rows[-20:]]) if len(rows)>=20 else 1
                pct_30=(closes[-1]-closes[0])/closes[0]*100
                vol_ratio=volumes[-1]/avg_vol if avg_vol>0 else 0
                if pct_30>3 and vol_ratio>1.2:
                    candidates.append({'code':code,'name':names.get(code,'?'),'pct_30':round(pct_30,1),'close':closes[-1],'vol_ratio':round(vol_ratio,1)})
            except: pass
        bs.logout()
    except: pass
    if i%60==0: print(f'  {i}/300')

candidates.sort(key=lambda x:x['pct_30'],reverse=True)
print(f'候选: {len(candidates)} 只')

buy_count=len([p for p in pf['positions'] if p['status']=='holding'])
for c in candidates[:6]:
    if buy_count>=3: break
    code=c['code']; name=c['name']; sc=code[3:]
    holding=any(p['code']==code and p['status']=='holding' for p in pf['positions'])
    if holding: print(f'  {sc} {name} 已持仓'); continue

    bs.login()
    rs=bs.query_history_k_data_plus(code,'date,open,close,high,low,volume',start_date=start,end_date=end,frequency='d',adjustflag='2')
    rows=[]
    while rs.next(): rows.append(rs.get_row_data())
    bs.logout()
    if len(rows)<30: continue
    
    df_k=pd.DataFrame(rows,columns=['date','open','close','high','low','volume'])
    for col in ['open','close','high','low','volume']: df_k[col]=pd.to_numeric(df_k[col])
    df_k['date']=pd.to_datetime(df_k['date'])
    df_k['MA5']=df_k['close'].rolling(5).mean(); df_k['MA20']=df_k['close'].rolling(20).mean()
    
    x=range(len(df_k))
    fig=plt.figure(figsize=(14,8))
    gs=fig.add_gridspec(2,1,height_ratios=[3,1],hspace=0.05)
    ax1=fig.add_subplot(gs[0]); ax2=fig.add_subplot(gs[1])
    colors=['#ff4444' if df_k['close'].iloc[i]>=df_k['open'].iloc[i] else '#00aa00' for i in x]
    for i in x:
        o,c_,h,l=df_k['open'].iloc[i],df_k['close'].iloc[i],df_k['high'].iloc[i],df_k['low'].iloc[i]
        ax1.plot([i,i],[l,h],color=colors[i],linewidth=0.8)
        ax1.add_patch(plt.Rectangle((i-0.3,min(o,c_)),0.6,abs(c_-o),color=colors[i],alpha=0.9))
    ax1.plot(x,df_k['MA5'],'b-',lw=1,label='MA5'); ax1.plot(x,df_k['MA20'],'orange',lw=1.5,label='MA20')
    ax1.set_title(f'{sc} {name} +{c["pct_30"]}%  {df_k["close"].iloc[-1]:.1f}',fontsize=14,fontweight='bold')
    ax1.legend(loc='upper left',fontsize=8); ax1.grid(True,alpha=0.3)
    vcolors=['#ff4444' if df_k['close'].iloc[i]>=df_k['open'].iloc[i] else '#00aa00' for i in x]
    ax2.bar(x,df_k['volume'],color=vcolors,alpha=0.6,width=0.8); ax2.grid(True,alpha=0.3)
    ticks=x[::15]; ax2.set_xticks(ticks)
    ax2.set_xticklabels([df_k['date'].iloc[i].strftime('%m/%d') for i in ticks],rotation=45,fontsize=8)
    plt.tight_layout()
    chart_path=str(CHARTS_DIR/f'{sc}.png')
    plt.savefig(chart_path,dpi=100,bbox_inches='tight'); plt.close()
    
    try:
        with open(chart_path,'rb') as f: img_b64=base64.b64encode(f.read()).decode()
        payload={'model':'qwen/qwen3-vl-4b','messages':[{'role':'user','content':[
            {'type':'image_url','image_url':{'url':f'data:image/png;base64,{img_b64}'}},
            {'type':'text','text':f'{sc} {name} 30日涨{c["pct_30"]}%。看图：能买吗？中文50字。'}
        ]}],'max_tokens':200,'temperature':0.3}
        req=urllib.request.Request('http://127.0.0.1:1234/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        resp=urllib.request.urlopen(req,timeout=90)
        analysis=json.loads(resp.read())['choices'][0]['message']['content']
        print(f'  {sc} {name} +{c["pct_30"]}%: {analysis[:150]}')
        
        buy_kw=['买入','可买','逢低','介入','布局','建仓','看涨','强势','持有']
        if any(kw in analysis for kw in buy_kw):
            price=c['close']; shares=int(pf['cash']*0.15/price/100)*100
            if shares>=100:
                cost=price*shares*1.003
                if cost<=pf['cash']:
                    pf['cash']-=cost
                    pf['positions'].append({'code':code,'name':name,'buy_price':price,'shares':shares,'buy_date':datetime.now().strftime('%Y-%m-%d'),'cost':cost,'reason':analysis[:100],'status':'holding','pnl_pct':0})
                    pf['history'].append({'type':'buy','code':code,'name':name,'price':price,'shares':shares,'date':datetime.now().strftime('%Y-%m-%d')})
                    buy_count+=1
                    print(f'  ✅ 买入 {shares}股 @{price:.2f} = {cost:,.0f}元')
        else:
            print(f'  ⏸ 观望')
    except Exception as e: print(f'  ❌ {e}')

with open(PORTFOLIO_FILE,'w',encoding='utf-8') as f: json.dump(pf,f,ensure_ascii=False,indent=2)

total=pf['cash']
for p in pf['positions']:
    if p['status']=='holding': total+=p.get('buy_price',0)*p['shares']
print(f'\n💰 现金:{pf["cash"]:,.0f} | 总资产:{total:,.0f}')
print(f'📈 持仓 {buy_count}:')
for p in pf['positions']:
    if p['status']=='holding': print(f'   {p["code"]} {p["name"]} {p["shares"]}股 @{p["buy_price"]:.1f}')
