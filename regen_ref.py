# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本")
import ref_lib
idx = ref_lib.load_index()
idx.pop("王半仙", None)
ref_lib.save_index(idx)
fn = ref_lib.ensure_ref("王半仙",
    "六十余岁的老人，瘦削长脸布满深刻皱纹，花白长发束成松散发髻，山羊胡，穿褪色深蓝灰长袍，袖口磨损",
    "江南镇书铺老板，落第老秀才")
print("regenerated:", fn)
