"""
Test Configuration — Lumio Backend
====================================

Pytest conftest that runs before test modules are imported.
Ensures an isolated temporary directory and sets mock environment variables.
"""

import os
import tempfile
from pathlib import Path

# Create an isolated temporary directory for test upload processing
_test_temp = tempfile.TemporaryDirectory(
    prefix="pytest-lumio-",
    dir=Path(__file__).resolve().parents[1] / "temp",
    ignore_cleanup_errors=True,
)

os.environ["LUMIO_TEMP_DIR"] = _test_temp.name
os.environ["GROQ_MODEL"] = "llama-3.3-70b-versatile"