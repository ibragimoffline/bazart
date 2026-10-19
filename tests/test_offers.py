"""Taklifli savdo: erkin narx, miqdor bo'yicha taklif, muzokara, zaxira va poyga.

Bu oqim pulga (deal summasi) va zaxiraga tegadi — har qoida chekka holatlar
bilan sinaladi. Haqiqiy parallel qabul qilish testi alohida ulanishlarda.
"""

import threading
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.deal import Deal
from app.models.enums import ItemStatus, OfferStatus, UserRole
from app.models.item import Item
from app.models.offer import Offer
from app.models.user import User
from app.services.offer_service import OfferService
from tests.conftest import AuthenticatedUser, create_user

# 150 000 so'm — mo'ljal narx (dona uchun), tiyinda.
ASKING = 15_000_000


def _listing(
    client: TestClient,
    seller: AuthenticatedUser,
    *,
    quantity: int = 10,
    publish: bool = True,
    title: str = "Samsung Galaxy Buds2 Pro",
) -> dict:
    item = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json={
            "title": title,
            "condition": "new",
            "starting_price": str(ASKING),
            "quantity": quantity,
        },
    )
    assert item.status_code == 201, item.text
    body = item.json()
    if publish:
        published = client.post(
            f"/api/v1/items/{body['id']}/publish",
            headers=seller.headers,
            json={"duration_days": 5},
        )
        assert published.status_code == 200, published.text
        body = published.json()
    return body


def _offer(client: TestClient, buyer: AuthenticatedUser, item_id: int, qty: int, unit: int):
    return client.post(
        f"/api/v1/items/{item_id}/offers",
        headers=buyer.headers,
        json={"quantity": qty, "unit_price": str(unit)},
    )


def _act(client: TestClient, user: AuthenticatedUser, offer_id: int, action: str, **body):
    return client.post(
        f"/api/v1/offers/{offer_id}/{action}", headers=user.headers, json=body or None
    )


def _item(client: TestClient, item_id: int) -> dict:
    return client.get(f"/api/v1/items/{item_id}").json()


def _users(client: TestClient, db: Session, *names: str) -> list[AuthenticatedUser]:
    return [create_user(client, db, email=f"{n}@example.com") for n in names]


# --- E'lon qilish ---------------------------------------------------------------


def test_publish_sets_offer_listing_with_deadline(client: TestClient, db_session: Session) -> None:
    (seller,) = _users(client, db_session, "seller")
    body = _listing(client, seller, quantity=10)
    assert body["listing_type"] == "offer"
    assert body["status"] == "active"
    assert body["quantity_total"] == 10
    assert body["quantity_available"] == 10
    assert body["listing_duration_days"] == 5
    ends = datetime.fromisoformat(body["listing_ends_at"])
    assert timedelta(days=4, hours=23) < ends - datetime.now(UTC) <= timedelta(days=5)


def test_publish_rules(client: TestClient, db_session: Session) -> None:
    seller, other = _users(client, db_session, "seller", "other")
    draft = _listing(client, seller, publish=False)
    url = f"/api/v1/items/{draft['id']}/publish"
    assert client.post(url, headers=other.headers, json={"duration_days": 5}).status_code == 403
    assert client.post(url, headers=seller.headers, json={"duration_days": 4}).status_code == 422
    assert client.post(url, headers=seller.headers, json={"duration_days": 3}).status_code == 200
    # Faol e'lonni qayta "e'lon qilish" yo'q.
    assert client.post(url, headers=seller.headers, json={"duration_days": 3}).status_code == 409


def test_auction_requires_single_unit_and_unpublished_item(
    client: TestClient, db_session: Session
) -> None:
    (seller,) = _users(client, db_session, "seller")
    now = datetime.now(UTC)
    auction = {
        "start_time": (now - timedelta(minutes=1)).isoformat(),
        "end_time": (now + timedelta(days=1)).isoformat(),
    }
    multi = _listing(client, seller, quantity=3, publish=False)
    resp = client.post(
        "/api/v1/auctions", headers=seller.headers, json={"item_id": multi["id"], **auction}
    )
    assert resp.status_code == 400

    offer_item = _listing(client, seller, quantity=1)
    resp = client.post(
        "/api/v1/auctions", headers=seller.headers, json={"item_id": offer_item["id"], **auction}
    )
    assert resp.status_code in (400, 409)

    single = _listing(client, seller, quantity=1, publish=False)
    resp = client.post(
        "/api/v1/auctions", headers=seller.headers, json={"item_id": single["id"], **auction}
    )
    assert resp.status_code == 201
    assert _item(client, single["id"])["listing_type"] == "auction"


def test_quantity_editable_only_before_publish(client: TestClient, db_session: Session) -> None:
    (seller,) = _users(client, db_session, "seller")
    draft = _listing(client, seller, quantity=2, publish=False)
    url = f"/api/v1/items/{draft['id']}"
    ok = client.patch(url, headers=seller.headers, json={"quantity": 7})
    assert ok.status_code == 200
    assert ok.json()["quantity_total"] == 7 and ok.json()["quantity_available"] == 7

    client.post(f"{url}/publish", headers=seller.headers, json={"duration_days": 3})
    assert client.patch(url, headers=seller.headers, json={"quantity": 9}).status_code == 409


# --- Erkin narx va miqdor --------------------------------------------------------


def test_any_positive_price_is_accepted_below_or_above_asking(
    client: TestClient, db_session: Session
) -> None:
    seller, low, high = _users(client, db_session, "seller", "low", "high")
    item = _listing(client, seller)

    cheap = _offer(client, low, item["id"], 2, ASKING // 3)  # mo'ljaldan ancha past
    assert cheap.status_code == 201, cheap.text
    rich = _offer(client, high, item["id"], 1, ASKING * 2)  # yuqori
    assert rich.status_code == 201

    body = cheap.json()
    assert body["status"] == "pending"
    assert body["awaiting"] == "seller"
    assert body["unit_price"] == str(ASKING // 3)
    assert body["total_price"] == str(2 * (ASKING // 3))
    # Keyingi taklif oldingisidan past bo'lishi ham mumkin — avtomatik rad yo'q.
    third_user = create_user(client, db_session, email="third@example.com")
    assert _offer(client, third_user, item["id"], 1, 100).status_code == 201


def test_offer_validation(client: TestClient, db_session: Session) -> None:
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller, quantity=3)
    assert _offer(client, buyer, item["id"], 4, ASKING).status_code == 409  # zaxiradan ko'p
    assert _offer(client, buyer, item["id"], 0, ASKING).status_code == 422
    assert _offer(client, buyer, item["id"], 1, 0).status_code == 422
    assert _offer(client, seller, item["id"], 1, ASKING).status_code == 400  # o'ziniki
    assert _offer(client, buyer, item["id"], 1, ASKING).status_code == 201
    # Bitta xaridor — bitta ochiq taklif (qarshi taklif / qaytarib olish bilan o'zgaradi).
    assert _offer(client, buyer, item["id"], 1, ASKING).status_code == 409

    draft = _listing(client, seller, publish=False)
    assert _offer(client, buyer, draft["id"], 1, ASKING).status_code == 409


# --- Qabul qilish, zaxira, deal -------------------------------------------------


def test_accept_creates_order_and_decrements_stock(client: TestClient, db_session: Session) -> None:
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller, quantity=10)
    offer = _offer(client, buyer, item["id"], 2, 12_000_000).json()

    # Xaridor o'z taklifini o'zi qabul qila olmaydi (navbat sotuvchida).
    assert _act(client, buyer, offer["id"], "accept").status_code == 409

    accepted = _act(client, seller, offer["id"], "accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["deal_id"] is not None

    deal = db_session.scalar(select(Deal).where(Deal.offer_id == offer["id"]))
    assert deal is not None
    assert deal.auction_id is None
    assert deal.quantity == 2
    assert deal.unit_price == 12_000_000
    assert deal.final_price == 24_000_000
    assert deal.buyer_id == buyer.id

    after = _item(client, item["id"])
    assert after["quantity_available"] == 8
    assert after["status"] == "active"


def test_selling_out_closes_remaining_offers(client: TestClient, db_session: Session) -> None:
    seller, a, b, c = _users(client, db_session, "seller", "a", "b", "c")
    item = _listing(client, seller, quantity=3)
    first = _offer(client, a, item["id"], 2, ASKING).json()
    second = _offer(client, b, item["id"], 1, ASKING).json()
    third = _offer(client, c, item["id"], 2, ASKING).json()

    assert _act(client, seller, first["id"], "accept").status_code == 200
    # 1 dona qoldi: 2 donali taklifni qabul qilib bo'lmaydi (oversell yo'q).
    assert _act(client, seller, third["id"], "accept").status_code == 409
    assert _act(client, seller, second["id"], "accept").status_code == 200

    after = _item(client, item["id"])
    assert after["quantity_available"] == 0
    assert after["status"] == "sold"
    db_session.expire_all()
    closed = db_session.get(Offer, third["id"])
    assert closed.status == OfferStatus.REJECTED
    assert closed.events[-1].action == "sold_out"


def test_cancelled_order_restores_stock(client: TestClient, db_session: Session) -> None:
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller, quantity=2)
    offer = _offer(client, buyer, item["id"], 2, ASKING).json()
    deal_id = _act(client, seller, offer["id"], "accept").json()["deal_id"]
    assert _item(client, item["id"])["status"] == "sold"

    cancel = client.post(
        f"/api/v1/deals/{deal_id}/cancel", headers=seller.headers, json={"reason": "changed_mind"}
    )
    assert cancel.status_code == 200, cancel.text
    after = _item(client, item["id"])
    assert after["quantity_available"] == 2
    assert after["status"] == "active"


def test_offer_order_records_line_total(client: TestClient, db_session: Session) -> None:
    """Deal jami = miqdor x dona narxi (to'lov oqimi yo'q — Faza E)."""
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller, quantity=5)
    offer = _offer(client, buyer, item["id"], 3, 1_000_000).json()
    deal_id = _act(client, seller, offer["id"], "accept").json()["deal_id"]

    deal = client.get(f"/api/v1/deals/{deal_id}", headers=buyer.headers).json()
    assert deal["quantity"] == 3
    assert deal["unit_price"] == "1000000"
    assert deal["final_price"] == "3000000"
    assert deal["offer_id"] == offer["id"]


# --- Muzokara -------------------------------------------------------------------


def test_counter_offer_round_trip(client: TestClient, db_session: Session) -> None:
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller, quantity=10)
    offer = _offer(client, buyer, item["id"], 4, 10_000_000).json()

    countered = _act(
        client,
        seller,
        offer["id"],
        "counter",
        quantity=4,
        unit_price="13000000",
        message="Eng past",
    )
    assert countered.status_code == 200, countered.text
    body = countered.json()
    assert body["awaiting"] == "buyer"
    assert body["unit_price"] == "13000000"
    assert [e["action"] for e in body["events"]] == ["offer", "counter"]

    # Sotuvchi o'z qarshi taklifini qabul qila olmaydi; navbat xaridorda.
    assert _act(client, seller, offer["id"], "accept").status_code == 409

    back = _act(client, buyer, offer["id"], "counter", quantity=3, unit_price="12000000")
    assert back.status_code == 200
    assert back.json()["awaiting"] == "seller"

    done = _act(client, seller, offer["id"], "accept")
    assert done.status_code == 200
    deal = db_session.scalar(select(Deal).where(Deal.offer_id == offer["id"]))
    assert (deal.quantity, deal.unit_price, deal.final_price) == (3, 12_000_000, 36_000_000)


def test_reject_and_withdraw_rules(client: TestClient, db_session: Session) -> None:
    seller, buyer, other = _users(client, db_session, "seller", "buyer", "other")
    item = _listing(client, seller)
    offer = _offer(client, buyer, item["id"], 1, ASKING).json()

    # Xaridor o'z kutilayotgan taklifini "rad eta" olmaydi — u qaytarib oladi.
    assert _act(client, buyer, offer["id"], "reject").status_code == 409
    assert _act(client, seller, offer["id"], "withdraw").status_code == 403
    assert _act(client, other, offer["id"], "accept").status_code == 404

    assert _act(client, buyer, offer["id"], "withdraw").json()["status"] == "withdrawn"
    # Yopilgan taklif bilan boshqa harakat yo'q; endi yangi taklif berish mumkin.
    assert _act(client, seller, offer["id"], "accept").status_code == 409
    second = _offer(client, buyer, item["id"], 1, ASKING)
    assert second.status_code == 201

    rejected = _act(client, seller, second.json()["id"], "reject")
    assert rejected.json()["status"] == "rejected"


def test_counter_cannot_exceed_stock(client: TestClient, db_session: Session) -> None:
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller, quantity=2)
    offer = _offer(client, buyer, item["id"], 1, ASKING).json()
    resp = _act(client, seller, offer["id"], "counter", quantity=5, unit_price=str(ASKING))
    assert resp.status_code == 409


# --- Muddatlar ------------------------------------------------------------------


def _shift(db: Session, model, obj_id: int, **fields) -> None:
    db.expire_all()
    row = db.get(model, obj_id)
    for key, value in fields.items():
        setattr(row, key, value)
    db.commit()


def test_expired_offer_cannot_be_accepted(client: TestClient, db_session: Session) -> None:
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller)
    offer = _offer(client, buyer, item["id"], 1, ASKING).json()
    assert datetime.fromisoformat(offer["expires_at"]) - datetime.now(UTC) > timedelta(hours=47)

    _shift(db_session, Offer, offer["id"], expires_at=datetime.now(UTC) - timedelta(minutes=1))
    assert _act(client, seller, offer["id"], "accept").status_code == 409
    assert (
        client.get(f"/api/v1/offers/{offer['id']}", headers=buyer.headers).json()["status"]
        == "expired"
    )
    assert _item(client, item["id"])["quantity_available"] == 10


def test_listing_expiry_job_and_republish(client: TestClient, db_session: Session) -> None:
    seller, buyer, late = _users(client, db_session, "seller", "buyer", "late")
    item = _listing(client, seller, quantity=4)
    offer = _offer(client, buyer, item["id"], 1, ASKING).json()
    _shift(db_session, Item, item["id"], listing_ends_at=datetime.now(UTC) - timedelta(minutes=1))

    # Job ishlamasa ham muddat o'tgan e'longa taklif berilmaydi.
    assert _offer(client, late, item["id"], 1, ASKING).status_code == 409

    assert OfferService(db_session).expire_due() == (0, 1)
    after = _item(client, item["id"])
    assert after["status"] == "expired"
    assert (
        client.get(f"/api/v1/offers/{offer['id']}", headers=buyer.headers).json()["status"]
        == "expired"
    )

    again = client.post(
        f"/api/v1/items/{item['id']}/publish", headers=seller.headers, json={"duration_days": 7}
    )
    assert again.status_code == 200
    assert again.json()["status"] == "active"
    assert again.json()["quantity_available"] == 4


def test_expiry_job_closes_stale_offers(client: TestClient, db_session: Session) -> None:
    seller, buyer = _users(client, db_session, "seller", "buyer")
    item = _listing(client, seller)
    offer = _offer(client, buyer, item["id"], 1, ASKING).json()
    _shift(db_session, Offer, offer["id"], expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert OfferService(db_session).expire_due() == (1, 0)
    assert OfferService(db_session).expire_due() == (0, 0)


# --- Bekor qilish va moderatsiya -------------------------------------------------


def test_cancel_listing_closes_offers_and_keeps_deals(
    client: TestClient, db_session: Session
) -> None:
    seller, a, b = _users(client, db_session, "seller", "a", "b")
    item = _listing(client, seller, quantity=5)
    sold = _offer(client, a, item["id"], 1, ASKING).json()
    deal_id = _act(client, seller, sold["id"], "accept").json()["deal_id"]
    open_offer = _offer(client, b, item["id"], 1, ASKING).json()

    resp = client.delete(f"/api/v1/items/{item['id']}", headers=seller.headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    assert (
        client.get(f"/api/v1/offers/{open_offer['id']}", headers=b.headers).json()["status"]
        == "rejected"
    )
    # Tuzilgan bitim o'z kuchida.
    assert client.get(f"/api/v1/deals/{deal_id}", headers=a.headers).status_code == 200


def test_admin_reject_cannot_be_republished(client: TestClient, db_session: Session) -> None:
    (seller,) = _users(client, db_session, "seller")
    admin = create_user(client, db_session, email="admin@example.com", role=UserRole.ADMIN)
    item = _listing(client, seller)
    reject = client.post(f"/api/v1/admin/items/{item['id']}/reject", headers=admin.headers)
    assert reject.status_code == 200
    assert reject.json()["status"] == "cancelled"
    republish = client.post(
        f"/api/v1/items/{item['id']}/publish", headers=seller.headers, json={"duration_days": 3}
    )
    assert republish.status_code == 409


# --- Maxfiylik ------------------------------------------------------------------


def test_offer_visibility(client: TestClient, db_session: Session) -> None:
    seller, buyer, other = _users(client, db_session, "seller", "buyer", "other")
    db_session.scalar(select(User).where(User.id == buyer.id)).full_name = "Alisher Karimov"
    db_session.commit()
    item = _listing(client, seller)
    offer = _offer(client, buyer, item["id"], 1, ASKING).json()

    assert client.get(f"/api/v1/offers/{offer['id']}", headers=other.headers).status_code == 404
    assert client.get(f"/api/v1/items/{item['id']}/offers", headers=other.headers).json() == []

    seller_view = client.get(f"/api/v1/items/{item['id']}/offers", headers=seller.headers).json()
    assert len(seller_view) == 1
    assert seller_view[0]["buyer_display"] != "Alisher Karimov"  # qabulgacha maskalangan

    received = client.get("/api/v1/offers?role=seller", headers=seller.headers).json()
    sent = client.get("/api/v1/offers?role=buyer", headers=buyer.headers).json()
    assert [o["id"] for o in received] == [offer["id"]] == [o["id"] for o in sent]
    assert sent[0]["item"]["title"] == "Samsung Galaxy Buds2 Pro"

    accepted = _act(client, seller, offer["id"], "accept").json()
    assert accepted["buyer_display"] == "Alisher Karimov"


def test_listing_type_filter(client: TestClient, db_session: Session) -> None:
    (seller,) = _users(client, db_session, "seller")
    offer_item = _listing(client, seller)
    _listing(client, seller, publish=False, title="Qoralama")
    listed = client.get("/api/v1/items?listing_type=offer&status=active").json()
    assert [i["id"] for i in listed] == [offer_item["id"]]


# --- Haqiqiy parallel qabul qilish (alohida ulanishlar) ---------------------------


def test_parallel_accepts_never_oversell(
    client: TestClient, db_session: Session, db_engine: Engine
) -> None:
    """3 dona, 8 ta xaridor 1 donadan — 8 ta parallel qabul. Aynan 3 tasi o'tishi shart.

    Qulf (item FOR UPDATE) olib tashlansa, bir nechta tranzaksiya bir xil zaxirani
    o'qib hammasi o'tadi — CHECK constraint yoki bu test yiqiladi.
    """
    seller = create_user(client, db_session, email="seller@example.com")
    buyers = [create_user(client, db_session, email=f"b{i}@example.com") for i in range(8)]
    item = _listing(client, seller, quantity=3)
    offer_ids = [_offer(client, b, item["id"], 1, ASKING).json()["id"] for b in buyers]

    SessionMaker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    barrier = threading.Barrier(len(offer_ids))
    results: list[str] = []
    lock = threading.Lock()

    def accept(offer_id: int) -> None:
        session = SessionMaker()
        try:
            actor = session.get(User, seller.id)
            barrier.wait()
            try:
                OfferService(session).accept(offer_id, actor)
                outcome = "ok"
            except Exception as exc:  # noqa: BLE001
                outcome = type(exc).__name__
            with lock:
                results.append(outcome)
        finally:
            session.close()

    threads = [threading.Thread(target=accept, args=(oid,)) for oid in offer_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 3, results
    check = SessionMaker()
    try:
        stored = check.get(Item, item["id"])
        assert stored.quantity_available == 0
        assert stored.status == ItemStatus.SOLD
        deals = check.scalars(select(Deal).where(Deal.item_id == item["id"])).all()
        assert sum(o.quantity for o in deals) == 3
    finally:
        check.close()
