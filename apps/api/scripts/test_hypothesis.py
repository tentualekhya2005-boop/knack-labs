import os
import sys
from pathlib import Path

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
print(f"DATABASE_URL setting value: {settings.database_url!r}")
print(f"DB_URL in os.environ: {'DB_URL' in os.environ}")
print(f"DATABASE_URL in os.environ: {'DATABASE_URL' in os.environ}")

try:
    from app.db.session import engine
    print(f"Engine created successfully: {engine.url}")
except Exception as e:
    print(f"Engine creation failed with error: {type(e).__name__}: {e}")
