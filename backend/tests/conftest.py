import os
import tempfile
from pathlib import Path


_test_chroma = tempfile.TemporaryDirectory(
	prefix="pytest-chroma-",
	dir=Path(__file__).resolve().parents[1] / "temp",
	ignore_cleanup_errors=True,
)
os.environ["LUMIO_CHROMA_DIR"] = _test_chroma.name