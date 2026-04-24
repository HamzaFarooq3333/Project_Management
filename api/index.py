"""
Vercel Serverless Function entrypoint.

Vercel runs this file as the Python handler. We expose the FastAPI `app`
defined in `app/main.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path (Vercel runs from /var/task/api)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

