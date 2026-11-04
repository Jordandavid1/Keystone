# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:/Users/Lesia Eden/Downloads/keystone-cowork/apps/web', 'apps/web'), ('C:/Users/Lesia Eden/Downloads/keystone-cowork/apps/admin', 'apps/admin'), ('C:/Users/Lesia Eden/Downloads/keystone-cowork/packages', 'packages'), ('C:/Users/Lesia Eden/Downloads/keystone-cowork/services', 'services'), ('C:/Users/Lesia Eden/Downloads/keystone-cowork/remote_config.json', '.')]
binaries = []
hiddenimports = ['uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.loops.asyncio', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'fastapi', 'pydantic', 'pydantic_core', 'sqlite3', 'aiosqlite', 'sqlalchemy', 'sqlalchemy.dialects.sqlite', 'sqlalchemy.dialects.sqlite.aiosqlite', 'greenlet', 'passlib', 'passlib.handlers.bcrypt', 'bcrypt', 'email_validator', 'webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium']
tmp_ret = collect_all('aiosqlite')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sqlalchemy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('passlib')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('bcrypt')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:/Users/Lesia Eden/Downloads/keystone-cowork/apps/desktop/launcher.py'],
    pathex=['C:/Users/Lesia Eden/Downloads/keystone-cowork'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='keystone-desktop',
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
