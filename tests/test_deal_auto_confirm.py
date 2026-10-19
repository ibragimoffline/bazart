"""Faza E2.7: 72 soatlik avto-tasdiq va shikoyat to'xtatishi (docs/DEALS.md §5).

"Sotildi" dan 72 soat o'tib, xaridor jim bo'lsa va kelishuv bo'yicha ochiq shikoyat bo'lmasa
kelishuv `completed` bo'ladi. Shikoyatni faqat kelishuv ishtirokchisi ocha oladi — aks holda
begona istalgan kelishuvni muzlatib qo'yardi.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.enums import UserRole
from app.services.deal_service import DealService
from app.tasks.scheduled import auto_confirm_deals_task
from tests.conftest import create_auction, create_bid, create_item, create_user


def _marked_deal(client: TestClient, db_session: Session, hours_ago: float):
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    create_bid(client, buyer, auction["id"], amount="1100")
    client.post(f"/api/v1/auctions/{auction['id']}/close", headers=seller.headers)
    deal_id = client.get("/api/v1/deals/buyer", headers=buyer.headers).json()[0]["id"]
    assert (
        client.post(f"/api/v1/deals/{deal_id}/complete", headers=seller.headers).status_code == 200
    )
    row = db_session.get(Deal, deal_id)
    row.seller_marked_sold_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    db_session.commit()
    return deal_id, seller, buyer


def _complain(client: TestClient, user, deal_id: int):
    return client.post(
        "/api/v1/complaints",
        headers=user.headers,
        json={"target_type": "deal", "target_id": deal_id, "reason": "Mahsulot boshqacha"},
    )


def _status(db_session: Session, deal_id: int) -> str:
    db_session.expire_all()
    return db_session.get(Deal, deal_id).status.value


def test_silent_buyer_is_auto_confirmed_after_72h(client: TestClient, db_session: Session) -> None:
    deal_id, _, _ = _marked_deal(client, db_session, hours_ago=73)
    assert DealService(db_session).auto_confirm_due() == 1
    assert _status(db_session, deal_id) == "completed"
    assert db_session.get(Deal, deal_id).completed_at is not None


def test_not_due_before_72h(client: TestClient, db_session: Session) -> None:
    deal_id, _, _ = _marked_deal(client, db_session, hours_ago=71)
    assert DealService(db_session).auto_confirm_due() == 0
    assert _status(db_session, deal_id) == "agreed"


def test_unmarked_deal_is_never_auto_confirmed(client: TestClient, db_session: Session) -> None:
    deal_id, _, _ = _marked_deal(client, db_session, hours_ago=73)
    row = db_session.get(Deal, deal_id)
    row.seller_marked_sold_at = None
    db_session.commit()
    assert DealService(db_session).auto_confirm_due() == 0


def test_open_complaint_blocks_auto_confirm(client: TestClient, db_session: Session) -> None:
    deal_id, _, buyer = _marked_deal(client, db_session, hours_ago=100)
    complaint = _complain(client, buyer, deal_id)
    assert complaint.status_code == 201, complaint.text
    assert DealService(db_session).auto_confirm_due() == 0
    assert _status(db_session, deal_id) == "agreed"

    admin = create_user(client, db_session, email="admin@example.com", role=UserRole.ADMIN)
    resolved = client.patch(
        f"/api/v1/complaints/{complaint.json()['id']}",
        headers=admin.headers,
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200, resolved.text
    assert DealService(db_session).auto_confirm_due() == 1


def test_stranger_cannot_complain_about_a_deal(client: TestClient, db_session: Session) -> None:
    deal_id, _, _ = _marked_deal(client, db_session, hours_ago=100)
    stranger = create_user(client, db_session, email="stranger@example.com")
    assert _complain(client, stranger, deal_id).status_code == 404
    assert _complain(client, stranger, 999999).status_code == 404


def test_celery_task_runs_the_job(client: TestClient, db_session: Session, monkeypatch) -> None:
    deal_id, _, _ = _marked_deal(client, db_session, hours_ago=73)
    monkeypatch.setattr("app.tasks.scheduled.SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    assert auto_confirm_deals_task() == 1
    assert _status(db_session, deal_id) == "completed"
