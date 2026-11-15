import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WD = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows'
for fn in ['视频去水印_LaMa轻量版.json', '视频去水印_LaMa高质量.json']:
    F = os.path.join(WD, fn)
    if not os.path.exists(F): continue
    d = json.load(open(F, encoding='utf-8'))
    n = 0
    for s in d['definitions']['subgraphs']:
        for node in s['nodes']:
            if node['type'] != 'AUSBOSS_NODES_RefineMask': continue
            wv = node.get('widgets_values')
            if isinstance(wv, list) and len(wv) > 6 and wv[6] == 'guided filter':
                wv[6] = 'off'; n += 1
            nm = node.get('widgets_values_named') or {}
            if nm.get('edge_refine') == 'guided filter':
                nm['edge_refine'] = 'off'; n += 1
            # guide_image 保留连接（off 时也不冲突，但留着以后想开可随时用）
    json.dump(d, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('%-34s edge_refine 改回 off: %d 处' % (fn, n))
