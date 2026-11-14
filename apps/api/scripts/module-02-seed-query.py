import sys
from pathlib import Path
from datetime import datetime, timezone

API_ROOT = Path(__file__).resolve().parent.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.session import SessionLocal
from app.models.link import Link


def main():
    db = SessionLocal()
    try:
        # Inserting a link with an existing code without handling unique collisions
        link = Link(
            code="gmrit-launch",
            long_url="https://gmrit.edu.in/du/duplicate-test",
            created_by="org_gmrit_002",
            created_at=datetime.now(timezone.utc),
        )
        db.add(link)
        db.commit()
        print(f"INSERTED_CODE: {link.code}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
