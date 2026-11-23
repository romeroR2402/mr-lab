# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: genera backend/dist/mrlab-backend/mrlab-backend.exe (modo onedir; Electron oculta la consola).
a = Analysis(
    ["run_backend.py"],
    pathex=["."],
    hiddenimports=["cryptography.hazmat.primitives.ciphers.aead", "cryptography.hazmat.primitives.kdf.scrypt"],
    excludes=["tkinter", "tests"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="mrlab-backend", console=True, upx=False)  # consola oculta por Electron (windowsHide)
coll = COLLECT(exe, a.binaries, a.datas, name="mrlab-backend", upx=False)
