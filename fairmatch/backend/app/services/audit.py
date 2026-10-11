from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, action: str, actor_id=None, target_type=None, target_id=None, ip=None, **details) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
            ip=ip,
        )
    )
