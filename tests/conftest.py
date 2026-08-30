from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Keep startup deterministic under pytest. Tests provide fake repositories and
# should not depend on live index creation or external Mongo availability.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SAFESPEAK_SKIP_STARTUP_INDEXES", "true")
os.environ.setdefault("RAG_ENABLE_OCR", "true")
os.environ.setdefault(
    "EVIDENCE_ENCRYPTION_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault(
    "EVIDENCE_AUDIT_SIGNING_KEY",
    "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
)
