"""Chemins, cible FPGA et fichiers dont dépend une synthèse."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # racine du dépôt
HERE = ROOT / "ExplorationHLS"
CPP = ROOT / "cpp"
HLS = ROOT / "hls"
CNN_TCL = HLS / "cnn.tcl"
WORK = HERE / "work"            # projets Catapult de l'exploration (ignoré par git : work/)


def runs_dir(fake: bool) -> Path:
    """Résultats versionnés (runs/) ; ceux du mode --fake à part (runs_fake/, ignoré par git)."""
    return HERE / ("runs_fake" if fake else "runs")


# Carte Zybo Z7-20 : XC7Z020-1CLG400C (DS190)
DEVICE = {"name": "xc7z020", "BRAM18": 280, "DSP": 220, "LUT": 53200}
CLOCK_NS = 10.0                 # horloge de hls/cnn.tcl (100 MHz)

# Tout ce qui change le matériel produit : si un de ces fichiers change, le projet de base est refait
# et les évaluations en cache ne sont plus réutilisées.
CODE_FILES = [CPP / "cnn.cpp", CPP / "cnn.hpp", CPP / "utils.cpp", CPP / "utils.hpp",
              CPP / "config.hpp", CPP / "coeffs_k5_raw.hpp", CNN_TCL]


def code_hash() -> str:
    h = hashlib.sha1()
    for f in CODE_FILES:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:10]
