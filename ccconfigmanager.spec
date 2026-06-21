# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CCConfigManager single-file executable."""

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(__file__).parent

a = Analysis(
    [str(ROOT / 'run.py')],
    pathex=[str(ROOT / 'src')],
    binaries=[],
    datas=[
        (str(ROOT / 'src' / 'ccconfigmanager' / 'static'), 'ccconfigmanager/static'),
    ],
    hiddenimports=[
        # uvicorn submodules loaded dynamically
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # fastapi / starlette internals
        'starlette',
        'starlette.middleware',
        # anthropic deps
        'httpx',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tcl',
        'matplotlib', 'pandas', 'numpy', 'scipy', 'PIL',
        'cryptography', 'bcrypt',
        'pydoc', 'doctest',
        'unittest', 'test',
        'sqlite3', 'sqlalchemy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CCConfigManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
