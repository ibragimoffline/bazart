from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditService:
    """Muhim harakatlarning o'zgarmas jurnaliga yozuvchi servis (INSERT only).

    Shikoyat ko'rib chiqilganda yagona ishonchli dalil — shu sababli audit yozuvi chaqiruvchining
    asosiy tranzaksiyasi ICHIDA bo'lishi shart. Bu servis HECH QACHON commit
    qilmaydi: faqat `add` + `flush`. Chaqiruvchi (admin harakatlari va h.k.)
    asosiy o'zgarish bilan BIRGA commit qiladi.

    Nega commit qilmaydi: agar audit alohida commit qilsa va keyin pul
    o'zgarishi rollback bo'lsa — jurnalda sodir bo'lmagan operatsiya qoladi
    (yolg'on dalil). Atomiklik uchun ikkalasi bitta tranzaksiyada.

    QOIDA: faqat yozish va o'qish. UPDATE/DELETE metodlari yo'q — jurnal
    o'zgarmas.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: int,
        actor_id: int | None = None,
        old_value: dict | None = None,
        new_value: dict | None = None,
        idempotency_key: str | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        """Bitta audit yozuvini yaratadi (commit QILMAYDI).

        `flush` yozuvni sessiyaga yuboradi va `id`/`created_at` ni to'ldiradi,
        ammo tranzaksiyani ochiq qoldiradi — chaqiruvchi commit qiladi.

        actor_id=None: worker yoki PSP webhook tomonidan qilingan operatsiya
        (odam aktori yo'q).
        """
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            old_value=old_value,
            new_value=new_value,
            idempotency_key=idempotency_key,
            ip=ip,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_for_entity(self, entity_type: str, entity_id: int) -> list[AuditLog]:
        """Berilgan obyektning butun jurnalini vaqt bo'yicha (eskidan yangiga) qaytaradi."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at, AuditLog.id)
        )
        return list(self.db.scalars(stmt).all())
