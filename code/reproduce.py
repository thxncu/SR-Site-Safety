#!/usr/bin/env python3
"""Regenerate the analyses from the supplied source records and fixed rules."""
import os, subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg")
commands = [
 [sys.executable, "code/reproduce_analysis.py", *sys.argv[1:]],
 [sys.executable, "code/compute_record_analysis.py"],
 [sys.executable, "code/compute_retrieval_robustness.py"],
 [sys.executable, "code/compute_relation_sensitivity.py"],
]
for command in commands:
 subprocess.run(command, cwd=root, env=env, check=True)
print("Analysis completed.")
