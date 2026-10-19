from sqlalchemy.orm import Session

from app.services.audit_service import AuditService


def test_record_persists_all_fields(db_session: Session) -> None:
    """record() barcha maydonlarni yozadi va JSONB dict aynan qaytadi."""
    service = AuditService(db_session)

    old_value = {"status": "active", "current_price": "6200050"}
    new_value = {"status": "cancelled", "reason": "shill"}

    entry = service.record(
        action="AUCTION_CANCELLED",
        entity_type="auction",
        entity_id=42,
        actor_id=None,
        old_value=old_value,
        new_value=new_value,
        idempotency_key="idem-key-1",
        ip="192.168.1.10",
    )
    # flush id/created_at ni to'ldiradi, ammo hali commit qilinmagan.
    assert entry.id is not None
    assert entry.created_at is not None

    db_session.commit()

    rows = service.list_for_entity("auction", 42)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "AUCTION_CANCELLED"
    assert row.entity_type == "auction"
    assert row.entity_id == 42
    assert row.actor_id is None
    assert row.idempotency_key == "idem-key-1"
    assert str(row.ip) == "192.168.1.10"
    # JSONB dict aynan (tur va qiymat bo'yicha) qaytadi.
    assert row.old_value == old_value
    assert row.new_value == new_value


def test_record_does_not_commit(db_session: Session) -> None:
    """record() commit QILMAYDI — chaqiruvchi rollback qilsa yozuv yo'qoladi.

    Bu atomiklik kafolati: audit asosiy tranzaksiya bilan birga bekor bo'ladi.
    """
    service = AuditService(db_session)
    service.record(action="AUCTION_CANCELLED", entity_type="auction", entity_id=7)

    # Chaqiruvchi tranzaksiyasi bekor bo'ldi (asosiy o'zgarish muvaffaqiyatsiz).
    db_session.rollback()

    assert service.list_for_entity("auction", 7) == []


def test_record_worker_actor_none(db_session: Session) -> None:
    """actor_id=None (worker) holati ishlaydi."""
    service = AuditService(db_session)
    service.record(
        action="AUCTION_CLOSED",
        entity_type="auction",
        entity_id=100,
        actor_id=None,
        new_value={"status": "ended"},
    )
    db_session.commit()

    rows = service.list_for_entity("auction", 100)
    assert len(rows) == 1
    assert rows[0].actor_id is None
    assert rows[0].old_value is None
    assert rows[0].new_value == {"status": "ended"}


def test_list_for_entity_ordered_and_scoped(db_session: Session) -> None:
    """list_for_entity vaqt bo'yicha tartibga soladi va faqat o'z obyektini qaytaradi."""
    service = AuditService(db_session)
    service.record(action="ORDER_CREATED", entity_type="deal", entity_id=5)
    service.record(action="ORDER_COMPLETED", entity_type="deal", entity_id=5)
    # Boshqa obyekt — aralashmasligi kerak.
    service.record(action="ORDER_CREATED", entity_type="deal", entity_id=6)
    db_session.commit()

    rows = service.list_for_entity("deal", 5)
    assert [r.action for r in rows] == ["ORDER_CREATED", "ORDER_COMPLETED"]
    assert all(r.entity_id == 5 for r in rows)
