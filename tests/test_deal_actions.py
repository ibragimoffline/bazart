"""Kelishuv amallari (Faza E2.3/E2.6): "Sotildi", "Tasdiqlayman", bekor qilish, aybdor tomon.

docs/DEALS.md §3, §5, §7. Holat faqat `deal_state` orqali; `completed`/`cancelled` yakuniy.
"""

import threading
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.deal import Deal
from app.models.user import User
from app.repositories.deal_repository import DealRepository
from app.services.deal_service import DealService
from tests.conftest import AuthenticatedUser, create_auction, create_bid, create_item, create_user


def _deal(
    client: TestClient, db_session: Session
) -> tuple[dict, AuthenticatedUser, AuthenticatedUser]:
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    create_bid(client, buyer, auction["id"], amount="1100")
    closed = client.post(f"/api/v1/auctions/{auction['id']}/close", headers=seller.headers)
    assert closed.status_code == 200, closed.text
    deal = client.get("/api/v1/deals/buyer", headers=buyer.headers).json()[0]
    return deal, seller, buyer


def _post(client: TestClient, user: AuthenticatedUser, deal_id: int, action: str, **body):
    return client.post(f"/api/v1/deals/{deal_id}/{action}", headers=user.headers, json=body or None)


def test_buyer_confirms_first_then_seller_mark_completes(
    client: TestClient, db_session: Session
) -> None:
    deal, seller, buyer = _deal(client, db_session)
    first = _post(client, buyer, deal["id"], "confirm")
    assert first.status_code == 200
    assert first.json()["status"] == "agreed"
    assert first.json()["buyer_confirmed_at"] is not None

    done = _post(client, seller, deal["id"], "complete")
    assert done.json()["status"] == "completed"


def test_roles_are_enforced(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer = _deal(client, db_session)
    assert _post(client, buyer, deal["id"], "complete").status_code == 403
    assert _post(client, seller, deal["id"], "confirm").status_code == 403


def test_changed_mind_blames_canceller(client: TestClient, db_session: Session) -> None:
    deal, _seller, buyer = _deal(client, db_session)
    body = _post(client, buyer, deal["id"], "cancel", reason="changed_mind").json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "changed_mind"
    assert body["cancelled_by_id"] == buyer.id
    assert body["at_fault_id"] == buyer.id


def test_not_as_described_blames_seller(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer = _deal(client, db_session)
    body = _post(client, buyer, deal["id"], "cancel", reason="not_as_described").json()
    assert body["at_fault_id"] == seller.id


def test_no_response_only_after_contact_window(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer = _deal(client, db_session)
    early = _post(client, seller, deal["id"], "cancel", reason="no_response")
    assert early.status_code == 409

    row = db_session.get(Deal, deal["id"])
    row.contacts_revealed_at = datetime.now(UTC) - timedelta(hours=49)
    db_session.commit()

    late = _post(client, seller, deal["id"], "cancel", reason="no_response")
    assert late.status_code == 200, late.text
    assert late.json()["at_fault_id"] == buyer.id


def test_final_states_are_final(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer = _deal(client, db_session)
    _post(client, seller, deal["id"], "complete")
    _post(client, buyer, deal["id"], "confirm")
    assert _post(client, buyer, deal["id"], "cancel", reason="other").status_code == 409


def test_no_action_on_cancelled_deal(client: TestClient, db_session: Session) -> None:
    """Bekor qilingan kelishuvga "Sotildi"/"Tasdiqlayman" vaqt ham yozmaydi."""
    deal, seller, buyer = _deal(client, db_session)
    _post(client, buyer, deal["id"], "cancel", reason="changed_mind")
    assert _post(client, seller, deal["id"], "complete").status_code == 409
    assert _post(client, buyer, deal["id"], "confirm").status_code == 409
    assert db_session.get(Deal, deal["id"]).seller_marked_sold_at is None


def test_parallel_mark_and_confirm_complete_the_deal(
    client: TestClient, db_session: Session, db_engine: Engine, monkeypatch
) -> None:
    """ "Sotildi" va "Tasdiqlayman" bir vaqtda: qulf bo'lmasa ikkalasi bir-birining yozuvini
    ko'rmay `agreed` da qotadi.

    Ikkala oqim qatorni o'qigach to'siqda (Barrier) uchrashadi. FOR UPDATE ishlasa ikkinchi
    oqim o'qishning o'zida kutadi, birinchisi to'siq vaqtini o'tkazib commit qiladi va
    ikkinchisi yangilangan qatorni ko'radi -> `completed`. Qulf olib tashlansa ikkalasi
    to'siqdan eski qator bilan o'tadi -> `agreed` (test yiqiladi).
    """
    deal, seller, buyer = _deal(client, db_session)
    barrier = threading.Barrier(2)
    original = DealRepository.get_for_update

    def slow_get_for_update(self, deal_id: int):
        row = original(self, deal_id)
        try:
            barrier.wait(timeout=1.5)
        except threading.BrokenBarrierError:
            pass
        return row

    monkeypatch.setattr(DealRepository, "get_for_update", slow_get_for_update)
    factory = sessionmaker(bind=db_engine)
    errors: list[BaseException] = []

    def run(user_id: int, action: str) -> None:
        with factory() as db:
            try:
                actor = db.get(User, user_id)
                getattr(DealService(db), action)(deal["id"], actor)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [
        threading.Thread(target=run, args=(seller.id, "complete")),
        threading.Thread(target=run, args=(buyer.id, "confirm")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    db_session.expire_all()
    assert db_session.get(Deal, deal["id"]).status.value == "completed"
