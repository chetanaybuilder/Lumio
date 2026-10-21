"""
Test Configuration — Lumio Backend
====================================

Pytest ``conftest.py`` that runs before any test module is imported.
It redirects the ChromaDB storage path to a temporary directory so that
tests never read or corrupt the development vector database.

The temporary directory is created under ``backend/temp/`` and is
automatically cleaned up when the test process exits.
"""

import os
import tempfile
from pathlib import Path

# Create an isolated temporary directory for test ChromaDB data.
# Using the project's own ``temp/`` folder keeps cleanup predictable.
_test_chroma = tempfile.TemporaryDirectory(
	prefix="pytest-chroma-",
	dir=Path(__file__).resolve().parents[1] / "temp",
	ignore_cleanup_errors=True,
)

# Override the environment variable before any application module imports
# ``config.py``, ensuring all tests use the isolated vector store.
os.environ["LUMIO_CHROMA_DIR"] = _test_chroma.name