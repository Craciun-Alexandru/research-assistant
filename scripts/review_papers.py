#!/usr/bin/env python3
"""Thin wrapper: deep-review scored papers."""
import subprocess
import sys

sys.exit(subprocess.call([sys.executable, "-m", "arxiv_digest.reviewer", *sys.argv[1:]]))
