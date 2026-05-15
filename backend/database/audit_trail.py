from typing import List, Optional

from sqlalchemy.orm import Session

from models.audit_trail import AuditTrail
from models.users import User


def create_audit_trail(
    db: Session,
    user: User,
    action: str,
) -> AuditTrail:
    audit = AuditTrail(
        user_id=user.id,
        action=action,
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return audit


def get_audit_trail(
    db: Session,
    audit_id: int,
) -> Optional[AuditTrail]:
    return (
        db.query(AuditTrail)
        .filter(AuditTrail.id == audit_id)
        .first()
    )


def get_all_audit_trails(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[AuditTrail]:
    return (
        db.query(AuditTrail)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_audit_trail(
    db: Session,
    audit_id: int,
    action: str,
) -> Optional[AuditTrail]:
    audit = (
        db.query(AuditTrail)
        .filter(AuditTrail.id == audit_id)
        .first()
    )

    if not audit:
        return None

    audit.action = action

    db.commit()
    db.refresh(audit)

    return audit


def delete_audit_trail(
    db: Session,
    audit_id: int,
) -> bool:
    audit = (
        db.query(AuditTrail)
        .filter(AuditTrail.id == audit_id)
        .first()
    )

    if not audit:
        return False

    db.delete(audit)
    db.commit()

    return True
