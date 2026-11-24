# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for music3 音乐工作室."""
import os
block_cipher = None

datas = [
    ('static', 'static'),
    ('assets', 'assets'),
    ('LICENSE', '.'),
    ('LICENSE-MINIMAX-MUSIC3.txt', '.'),
    ('THIRD-PARTY-NOTICES.md', '.'),
]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['PIL', 'numpy', 'matplotlib', 'pandas', 'scipy', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    [],
    name='music3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version='version_info.txt',
)
