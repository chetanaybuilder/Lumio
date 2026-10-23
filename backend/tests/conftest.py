"""
Test Configuration — Lumio Backend
====================================

Pytest conftest that runs before test modules are imported.
Ensures an isolated temporary directory and sets mock environment variables.
"""

import os
import sys
import tempfile
from pathlib import Path

# Ensure backend and root are in sys.path for test discovery and imports
_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Create an isolated temporary directory for test upload processing
_test_temp = tempfile.TemporaryDirectory(
    prefix="pytest-lumio-",
    dir=Path(__file__).resolve().parents[1] / "temp",
    ignore_cleanup_errors=True,
)

os.environ["LUMIO_TEMP_DIR"] = _test_temp.name
os.environ["CLOUDFLARE_ACCOUNT_ID"] = "mock_account_id"
os.environ["CLOUDFLARE_API_TOKEN"] = "mock_api_token"
os.environ["CLOUDFLARE_MODEL"] = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
os.environ["CLOUDFLARE_FALLBACK_MODEL"] = "@cf/meta/llama-3.1-8b-instruct-fp8"