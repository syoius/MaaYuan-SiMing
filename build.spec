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
        'win32api',
        'backend.app',
        'backend.fight_g',
        'flask',
        'flask_cors'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'cefpython3',
        'setuptools',
        'pip',
        'xml',
        'unittest',
        'test',
        'distutils',
        'pkg_resources'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    workpath=os.path.join('build')
)

# 清空默认的二进制文件列表
a.binaries = [x for x in a.binaries if not any(
    pattern in x[0].lower() for pattern in [
        'cefpython3',
        'python27',
        'python34',
        'python35',
        'python36',
        'python37',
        'python38',
        'python39',
    ]
)]

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
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/static/icon.ico'
)