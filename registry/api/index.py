"""Vercel serverless entrypoint — exposes the FastAPI app as an ASGI function."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402

# Vercel's Python runtime detects the ASGI `app` object.
