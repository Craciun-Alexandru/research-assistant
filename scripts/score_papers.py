#!/usr/bin/env python3
"""Thin wrapper: score filtered papers."""
import subprocess
import sys

sys.exit(subprocess.call([sys.executable, "-m", "arxiv_digest.scorer", *sys.argv[1:]]))
