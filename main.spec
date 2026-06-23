# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('C:/Anaconda3/envs/qt310/Library/bin/libexpat.dll', '.'),
    ],
    datas=[
        ('mapping/mapping_data.txt', 'mapping'),
        ('mapping/mapping_pic.txt', 'mapping'),
        ('assets/pic.ico', 'assets'),
    ],
    hiddenimports=[
        'openpyxl',
        'pypinyin',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngine',
        'src',
        'src.worker',
        'src.Excel_Handler',
        'src.Excel_Info',
        'src.Excel_Writer',
        'src.File_Reader',
        'src.Name_Matcher',
        'window',
        'window.table_qt',
        'window.table_qt_2',
        'window.table_conbine',
        'window.settings_dialog',
        'xml.etree.ElementTree',
        'xml.parsers.expat',
    ],
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
    name='Excel誊写器3.0',
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
    icon=['assets/pic.ico'],
)
