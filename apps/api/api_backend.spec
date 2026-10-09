# -*- mode: python ; coding: utf-8 -*-
"""Freeze the YtPop API backend for packaged desktop runs (D7).

    python -m PyInstaller api_backend.spec --noconfirm
    -> dist-frozen/api-backend/api-backend(.exe)

Torch/sentence-transformers are deliberately EXCLUDED (they only back the
optional MiniLM embedder; the app falls back to Ollama embeddings, see
app/services/embedding_service.py). Excluding them keeps the freeze small
enough to ship; transcriptions still work because faster-whisper uses
ctranslate2, which is included.
"""

import os
import shutil
import sys

block_cipher = None

EXCLUDES = [
    "torch", "torch.*",
    "sentence_transformers", "sentence_transformers.*",
    "transformers", "transformers.*",
    "matplotlib", "matplotlib.*",
    "notebook", "notebook.*",
    "IPython", "IPython.*",
    "pytest", "pytest.*",
    "tkinter", "tkinter.*",
    "PyInstaller", "PyInstaller.*",
]

HIDDEN = [
    "app.main",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "dotenv",
    "yaml",
    "httpx",
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(
    [os.path.abspath("api_backend.py")],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="api-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="api-backend",
)

bundle_dir = os.path.join("dist-frozen", "api-backend")
os.makedirs(bundle_dir, exist_ok=True)

# Ship the whole ffmpeg tool folder next to the frozen backend so the
# packaged app needs nothing on PATH. Shared ffmpeg builds need their
# sibling DLLs, so copy every file from the directory of the resolved
# binary (not just the .exe).
src_dir = shutil.which("ffmpeg")
if src_dir:
    src_dir = os.path.dirname(src_dir)
    copied = 0
    for name in sorted(os.listdir(src_dir)):
        source = os.path.join(src_dir, name)
        if not os.path.isfile(source):
            continue
        if not name.lower().endswith((".exe", ".dll")):
            continue
        dest = os.path.join(bundle_dir, name)
        try:
            shutil.copy2(source, dest)
            copied += 1
        except OSError as e:
            print(f"[spec] could not bundle {name}: {e}", file=sys.stderr)
    print(f"[spec] bundled {copied} files from {src_dir}")
else:
    print("[spec] ffmpeg not found on PATH - packaged ffmpeg will be missing",
          file=sys.stderr)
