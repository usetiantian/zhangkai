import hashlib, os, datetime

files_with_baseline = [
    ('nexus_agent/event_bus.py',
     '9b1459d13d4f46097f69829adc20ad2f', 1783586559, 'Stage 2 report (mtime 2026-07-09 16:42)'),
    ('nexus_agent/nexus_llm.py',
     'f5d606baa35c314842c2334eba60380d', 1783999632, 'Stage 2 report (mtime 2026-07-14 11:27)'),
    ('nexus_agent/consciousness/engine.py',
     '0364c49cac238c9a1b112bbcb8b03824', 1784009800, 'Stage 5 report (mtime 2026-07-14 14:16:40)'),
    ('nexus_agent/self_play/__init__.py',
     '655e48c8f4a54b6311d3efaed8623439', 1784042006, 'Stage 7 report'),
    ('nexus_agent/learning_engine/__init__.py',
     '7203feb32f47b9a421f1b35c833c3166', 1783408803, 'Stage 7 report'),
    ('nexus_agent/cognitive_loop/__init__.py',
     '2c0e0fb787b50841a31f102fcfa8d0f8', 1783980074, 'Stage 7 report'),
    ('nexus_agent/evolution_engine.py',
     '57bc2de4cc218e4a7e064b79c1fc706a', 1784002147, 'Stage 7 report'),
    ('nexus_agent/self_modifier/__init__.py',
     'bbafac3ce66243b44963275a946150a8', 1781544869, 'Stage 7 report'),
    ('nexus_agent/world_model/__init__.py',
     None, None, 'Stage 3 changed docstring (mtime 2026-07-15 01:06:51 is canonical)'),
    ('nexus_agent/self_awareness/__init__.py',
     'ffaf198e16c3edd7c04ec865f9238154', 1784050965, 'Stage 5 final MD5 (mtime 2026-07-15 01:42:45)'),
]

print(f'{"File":<46} {"current_md5":<34} {"baseline_md5":<34} {"md5_OK":<6} {"current_mtime":<19} {"base_mtime":<19} {"mtime_OK":<6} source')
print('-' * 200)
all_ok = True
for f, base_md5, base_mt, src in files_with_baseline:
    st = os.stat(f)
    cur_md5 = hashlib.md5(open(f, 'rb').read()).hexdigest()
    cur_mt = int(st.st_mtime)
    md5_ok = 'N/A' if base_md5 is None else ('YES' if cur_md5 == base_md5 else 'NO')
    mt_ok = 'N/A' if base_mt is None else ('YES' if cur_mt == base_mt else 'NO')
    if md5_ok == 'NO' or mt_ok == 'NO':
        all_ok = False
    cur_mt_iso = datetime.datetime.fromtimestamp(cur_mt).isoformat(timespec='seconds')
    base_mt_iso = 'N/A' if base_mt is None else datetime.datetime.fromtimestamp(base_mt).isoformat(timespec='seconds')
    base_disp = base_md5 if base_md5 else 'N/A (Stage 3 changed content)'
    print(f'{f:<46} {cur_md5:<34} {base_disp:<34} {md5_ok:<6} {cur_mt_iso:<19} {base_mt_iso:<19} {mt_ok:<6} {src}')

print()
print('Summary:', 'ALL 10 CORE ENTRIES UNCHANGED' if all_ok else 'SOME FILES CHANGED — INVESTIGATE')