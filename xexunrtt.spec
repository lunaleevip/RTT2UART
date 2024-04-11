# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main_window.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

win_extra = [('product_version', '2.0.1'),
             ('file_version', '2.0.1'),
             ('comments', 'a jlink_rtt tools'),
             ('company_name', 'Xexun'),
             ('product_name', 'xexunrtt'),
             ('internal_name', 'xexunrtt')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='xexunrtt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['jlink_icon.ico'],
    win_extra=win_extra
)
