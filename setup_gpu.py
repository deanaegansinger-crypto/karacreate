"""Swaps the CPU build of PyTorch for the NVIDIA (CUDA) build of the same
version, so vocal removal and transcription run on the graphics card."""

import subprocess
import sys

import torch
import torchaudio

if torch.cuda.is_available():
    print("PyTorch can already use the graphics card.")
    sys.exit(0)

versions = [f"torch=={torch.__version__.split('+')[0]}", f"torchaudio=={torchaudio.__version__.split('+')[0]}"]
for cuda in ("cu128", "cu126", "cu124", "cu121"):
    print(f"Trying the {cuda} build of {' '.join(versions)}...")
    cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", *versions,
           "--index-url", f"https://download.pytorch.org/whl/{cuda}"]
    if subprocess.run(cmd).returncode == 0:
        print("Installed the graphics-card build of PyTorch.")
        sys.exit(0)
print("Couldn't find a graphics-card build to match: Karaoke Maker will use the CPU (slower, but works).")
