# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[
        os.path.dirname(os.path.abspath(SPECPATH))
    ],
    binaries=[],
    datas=[
        ('frontend/index.html', 'frontend'),
        ('frontend/static/icon.ico', 'frontend/static'),
        ('backend/templates/fight_action.json', 'backend/templates'),
        ('backend/fight_g.py', 'backend'),
        ('backend/data', 'backend/data'),
        ('backend/app.py', 'backend'),
        ('backend/__init__.py', 'backend'),
    ],
    hiddenimports=[
        'webview',
        'pythoncom',
        'win32api',
        'backend.app',
        'backend',
        'backend.fight_g',
        'flask',
        'flask_cors'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    workpath=os.path.join('build')
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MaaYuan_SiMing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/static/icon.ico'
) 