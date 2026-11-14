import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal
from app.models.link import Link


def test_duplicate_code_triggers_integrity_error():
    db = SessionLocal()
    code = "collision-test-code"
    try:
        existing = db.query(Link).filter(Link.code == code).first()
        if existing:
            db.delete(existing)
            db.commit()

        link1 = Link(
            code=code,
            long_url="https://gmrit.edu.in/du",
            created_by="org_001",
            created_at=datetime.now(timezone.utc),
        )
        db.add(link1)
        db.commit()

        link2 = Link(
            code=code,
            long_url="https://gmrit.edu.in/du/duplicate",
            created_by="org_002",
            created_at=datetime.now(timezone.utc),
        )
        db.add(link2)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        existing = db.query(Link).filter(Link.code == code).first()
        if existing:
            db.delete(existing)
            db.commit()
        db.close()

