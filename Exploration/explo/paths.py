"""Chemins et compilateur. Les autres modules lisent `paths.X` à l'exécution (modifiable pour les tests)."""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent      # Exploration/
ROOT = HERE.parent                                  # racine du dépôt
CPP = ROOT / "cpp"
BUILD = HERE / "build"
RUNS = HERE / "runs"
CACHE_FILE = RUNS / "cache.jsonl"                   # une ligne par évaluation (ajout seulement)
OLD_CACHE_FILE = RUNS / "cache.json"                # ancien format, encore lu
SELECTED_FILE = RUNS / "selected.json"
SESSIONS = RUNS / "sessions"

CXX = os.environ.get("CXX", "g++")
CXXFLAGS = ["-std=c++17", "-O2"]
