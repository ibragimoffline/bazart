from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.models.deal import Deal
from app.models.enums import ComplaintStatus, ComplaintTargetType, is_admin
from app.models.user import User
from app.repositories.complaint_repository import ComplaintRepository

# Yakuniy holatlar: bularga o'tgach resolved_by/resolved_at yoziladi va
# qayta ochilmaydi (audit uchun).
_TERMINAL_STATUSES = (ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED)


class ComplaintService:
    """Shikoyat oqimi: foydalanuvchi yaratadi, admin ko'rib chiqadi.

    Oddiy foydalanuvchi faqat yarata oladi va faqat o'zining shikoyatini
    ko'radi (bu yerda create). Ro'yxat va status o'zgartirish — faqat admin.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.complaints = ComplaintRepository(db)

    def create(
        self,
        reporter: User,
        target_type: ComplaintTargetType,
        target_id: int,
        reason: str,
        description: str | None,
    ) -> Complaint:
        if target_type == ComplaintTargetType.DEAL:
            # Kelishuv shikoyati avto-tasdiqni to'xtatadi — begona shikoyat bilan istalgan
            # kelishuvni muzlatib bo'lmasin. Ishtirokchi emas yoki yo'q — 404 (IDOR).
            deal = self.db.get(Deal, target_id)
            if deal is None or reporter.id not in {deal.buyer_id, deal.seller_id}:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        complaint = self.complaints.create(
            reporter_id=reporter.id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            description=description,
        )
        self.db.commit()
        self.db.refresh(complaint)
        return complaint

    def list_for_admin(
        self, admin: User, status_filter: ComplaintStatus | None = None
    ) -> list[Complaint]:
        if not is_admin(admin.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )
        return self.complaints.list_all(status_filter)

    def update_status(
        self, complaint_id: int, admin: User, new_status: ComplaintStatus
    ) -> Complaint:
        if not is_admin(admin.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )

        complaint = self.complaints.get(complaint_id)
        if complaint is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

        complaint.status = new_status
        if new_status in _TERMINAL_STATUSES:
            complaint.resolved_by_id = admin.id
            complaint.resolved_at = datetime.now(UTC)
        else:
            # Yakuniy holatdan qaytarilsa (masalan REVIEWING'ga) — hal belgilari tozalanadi.
            complaint.resolved_by_id = None
            complaint.resolved_at = None

        self.complaints.save(complaint)
        self.db.commit()
        self.db.refresh(complaint)
        return complaint
