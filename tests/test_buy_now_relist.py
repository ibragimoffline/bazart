"""Buy-now, sotilmagan lotni qayta joylash va "tugashiga oz qoldi" eslatmasi.

Buy-now pul oqimiga kiradi (deal + yakuniy narx), relist esa bitta tovarni
ikki marta sotish teshigini ochishi mumkin edi — shuning uchun ikkalasi ham
chekka holatlar bilan sinaladi.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.bid import Bid
from app.models.deal import Deal
from app.models.enums import AuctionStatus, BidStatus, NotificationType, UserRole
from app.models.item import ItemImage
from app.models.notification import Notification
from app.services.auction_closer import close_due_auctions
from app.services.ending_soon import notify_ending_soon
from tests.conftest import AuthenticatedUser, create_bid, create_item, create_user


def _create_auction(
    client: TestClient,
    seller: AuthenticatedUser,
    item_id: int,
    *,
    end_delta: timedelta = timedelta(days=1),
    reserve_price: str | None = None,
    buy_now_price: str | None = None,
) -> dict:
    now = datetime.now(UTC)
    payload: dict = {
        "item_id": item_id,
        "start_time": (now - timedelta(minutes=1)).isoformat(),
        "end_time": (now + end_delta).isoformat(),
        "minimum_bid_increment": "100",
    }
    if reserve_price is not None:
        payload["reserve_price"] = reserve_price
    if buy_now_price is not None:
        payload["buy_now_price"] = buy_now_price
    return client.post("/api/v1/auctions", headers=seller.headers, json=payload)


def _expire(db_session: Session, auction_id: int) -> None:
    db_session.expire_all()
    auction = db_session.get(Auction, auction_id)
    assert auction is not None
    auction.end_time = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(auction)
    db_session.commit()


def _relist(client: TestClient, user: AuthenticatedUser, auction_id: int, **overrides):
    body = {"duration_days": 5, "starting_price": "900", **overrides}
    return client.post(f"/api/v1/auctions/{auction_id}/relist", headers=user.headers, json=body)


# --- Buy-now ------------------------------------------------------------------


def test_buy_now_price_must_be_above_starting_price(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    response = _create_auction(client, seller, item["id"], buy_now_price="1000")
    assert response.status_code == 400


def test_buy_now_price_cannot_be_below_reserve(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    response = _create_auction(
        client, seller, item["id"], reserve_price="5000", buy_now_price="3000"
    )
    assert response.status_code == 400


def test_buy_now_ends_auction_and_creates_order(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], buy_now_price="5000").json()
    assert auction["buy_now_price"] == "5000"
    assert auction["buy_now_available"] is True

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ended"
    assert body["winner_id"] == buyer.id
    assert body["current_price"] == "5000"
    assert body["buy_now_available"] is False

    deal = db_session.scalar(select(Deal).where(Deal.auction_id == auction["id"]))
    assert deal is not None
    assert deal.buyer_id == buyer.id
    assert deal.final_price == 5000
    assert client.get(f"/api/v1/items/{item['id']}").json()["status"] == "sold"

    types = {(n.user_id, n.type) for n in db_session.scalars(select(Notification)).all()}
    assert (buyer.id, NotificationType.WON) in types
    assert (seller.id, NotificationType.SOLD) in types


def test_buy_now_closes_after_first_bid(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], buy_now_price="5000").json()

    create_bid(client, bidder, auction["id"], amount="1100")
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["buy_now_available"] is False

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 409
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "active"


def test_seller_cannot_buy_own_lot(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], buy_now_price="5000").json()

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=seller.headers)
    assert response.status_code == 400


def test_second_buy_now_conflicts(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    first = create_user(client, db_session, email="first@example.com")
    second = create_user(client, db_session, email="second@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], buy_now_price="5000").json()

    url = f"/api/v1/auctions/{auction['id']}/buy-now"
    assert client.post(url, headers=first.headers).status_code == 200
    assert client.post(url, headers=second.headers).status_code == 409
    deals = db_session.scalars(select(Deal).where(Deal.auction_id == auction["id"])).all()
    assert len(deals) == 1


def test_buy_now_without_price_conflicts(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()
    assert auction["buy_now_available"] is False

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 409


# --- Relist -------------------------------------------------------------------


def test_relist_unsold_auction_creates_new_listing(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, title="Samsung Galaxy S23", starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()
    _expire(db_session, auction["id"])
    assert close_due_auctions(db_session) == 1

    response = _relist(client, seller, auction["id"], buy_now_price="3000")
    assert response.status_code == 201
    new_auction = response.json()
    assert new_auction["id"] != auction["id"]
    assert new_auction["status"] == "active"
    assert new_auction["starting_price"] == "900"
    assert new_auction["current_price"] == "900"
    assert new_auction["buy_now_price"] == "3000"
    assert new_auction["duration_days"] == 5

    new_item = client.get(f"/api/v1/items/{new_auction['item_id']}").json()
    assert new_item["title"] == "Samsung Galaxy S23"
    assert new_item["relisted_from_id"] == item["id"]
    assert new_item["status"] == "active"
    # Eski auksion o'zgarmaydi.
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "ended"


def test_relist_twice_conflicts(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()
    _expire(db_session, auction["id"])
    close_due_auctions(db_session)

    assert _relist(client, seller, auction["id"]).status_code == 201
    assert _relist(client, seller, auction["id"]).status_code == 409


def test_cannot_relist_sold_or_live_auction(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    live_item = create_item(client, seller, starting_price="1000")
    live = _create_auction(client, seller, live_item["id"]).json()
    assert _relist(client, seller, live["id"]).status_code == 409

    sold_item = create_item(client, seller, starting_price="1000")
    sold = _create_auction(client, seller, sold_item["id"]).json()
    create_bid(client, bidder, sold["id"], amount="1100")
    _expire(db_session, sold["id"])
    close_due_auctions(db_session)
    assert _relist(client, seller, sold["id"]).status_code == 409


def test_other_user_cannot_relist(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    other = create_user(client, db_session, email="other@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()
    _expire(db_session, auction["id"])
    close_due_auctions(db_session)

    assert _relist(client, other, auction["id"]).status_code == 403


def test_relist_rejects_bad_pricing(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()
    _expire(db_session, auction["id"])
    close_due_auctions(db_session)

    assert _relist(client, seller, auction["id"], buy_now_price="900").status_code == 400
    assert _relist(client, seller, auction["id"], reserve_price="500").status_code == 400
    # Rad etilgan urinishlar qayta joylashni "band qilmaydi".
    assert _relist(client, seller, auction["id"]).status_code == 201


def test_relist_closes_open_second_chance(client: TestClient, db_session: Session) -> None:
    """Qayta joylangach eski second-chance qabul qilinmaydi — tovar ikki marta sotilmasin."""
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], reserve_price="5000").json()
    create_bid(client, bidder, auction["id"], amount="1100")
    _expire(db_session, auction["id"])
    close_due_auctions(db_session)
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "reserve_not_met"

    assert _relist(client, seller, auction["id"]).status_code == 201

    accept = client.post(
        f"/api/v1/auctions/{auction['id']}/second-chance/accept", headers=seller.headers
    )
    assert accept.status_code == 409
    assert db_session.scalar(select(Deal).where(Deal.auction_id == auction["id"])) is None


# --- Seller filtri (My listings) ----------------------------------------------


def test_list_auctions_filters_by_seller(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    other = create_user(client, db_session, email="other@example.com")
    mine = _create_auction(client, seller, create_item(client, seller)["id"]).json()
    _create_auction(client, other, create_item(client, other)["id"])

    response = client.get(f"/api/v1/auctions?status=active&seller_id={seller.id}")
    assert response.status_code == 200
    assert [a["id"] for a in response.json()] == [mine["id"]]


# --- Ending soon --------------------------------------------------------------


def _ending_soon_recipients(db_session: Session) -> list[int]:
    rows = db_session.scalars(
        select(Notification).where(Notification.type == NotificationType.ENDING_SOON)
    ).all()
    return sorted(n.user_id for n in rows)


def test_ending_soon_notifies_watchers_and_bidders_once(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    outbid = create_user(client, db_session, email="outbid@example.com")
    leader = create_user(client, db_session, email="leader@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], end_delta=timedelta(minutes=30)).json()
    client.post("/api/v1/watchlist", headers=watcher.headers, json={"auction_id": auction["id"]})
    client.post("/api/v1/watchlist", headers=seller.headers, json={"auction_id": auction["id"]})
    create_bid(client, outbid, auction["id"], amount="1100")
    create_bid(client, leader, auction["id"], amount="1300")

    assert notify_ending_soon(db_session) == 1
    assert _ending_soon_recipients(db_session) == sorted([watcher.id, outbid.id, leader.id])

    leader_note = db_session.scalar(
        select(Notification).where(
            Notification.type == NotificationType.ENDING_SOON,
            Notification.user_id == leader.id,
        )
    )
    assert leader_note is not None
    assert "yetakchisiz" in (leader_note.body or "")

    # Takroriy tik yangi eslatma yubormaydi.
    assert notify_ending_soon(db_session) == 0
    assert len(_ending_soon_recipients(db_session)) == 3


def test_ending_soon_skips_far_and_closed_auctions(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    far = _create_auction(client, seller, create_item(client, seller)["id"]).json()
    client.post("/api/v1/watchlist", headers=watcher.headers, json={"auction_id": far["id"]})

    assert notify_ending_soon(db_session) == 0
    assert _ending_soon_recipients(db_session) == []

    db_session.expire_all()
    stored = db_session.get(Auction, far["id"])
    assert stored is not None
    assert stored.status == AuctionStatus.ACTIVE
    assert stored.ending_soon_notified_at is None


# --- Review tuzatishlari ------------------------------------------------------


def _admin(client: TestClient, db_session: Session) -> AuthenticatedUser:
    return create_user(client, db_session, email="admin@example.com", role=UserRole.ADMIN)


def test_blocked_user_cannot_buy_now_or_relist(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    lot_item = create_item(client, seller, starting_price="1000")
    lot = _create_auction(client, seller, lot_item["id"], buy_now_price="5000").json()
    unsold_item = create_item(client, seller, starting_price="1000")
    unsold = _create_auction(client, seller, unsold_item["id"]).json()
    _expire(db_session, unsold["id"])
    close_due_auctions(db_session)

    assert client.post(f"/api/v1/admin/users/{buyer.id}/block", headers=admin.headers).is_success
    assert client.post(f"/api/v1/admin/users/{seller.id}/block", headers=admin.headers).is_success

    buy = client.post(f"/api/v1/auctions/{lot['id']}/buy-now", headers=buyer.headers)
    assert buy.status_code in (401, 403)
    assert _relist(client, seller, unsold["id"]).status_code in (401, 403)


def test_admin_can_cancel_listing_with_live_auction(
    client: TestClient, db_session: Session
) -> None:
    admin = _admin(client, db_session)
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()
    create_bid(client, bidder, auction["id"], amount="1100")

    response = client.delete(f"/api/v1/items/{item['id']}", headers=admin.headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "cancelled"


def test_admin_reject_stops_auction_and_blocks_relist(
    client: TestClient, db_session: Session
) -> None:
    admin = _admin(client, db_session)
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()

    reject = client.post(f"/api/v1/admin/items/{item['id']}/reject", headers=admin.headers)
    assert reject.status_code == 200
    assert reject.json()["status"] == "cancelled"
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "cancelled"
    # Rad etilgan e'lon qayta joylash orqali qaytib kelmaydi.
    assert _relist(client, seller, auction["id"]).status_code == 409


def test_admin_cancel_uses_state_machine(client: TestClient, db_session: Session) -> None:
    admin = _admin(client, db_session)
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"]).json()
    create_bid(client, bidder, auction["id"], amount="1100")
    _expire(db_session, auction["id"])
    close_due_auctions(db_session)

    url = f"/api/v1/admin/auctions/{auction['id']}/cancel"
    assert client.post(url, headers=admin.headers).status_code == 409
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "ended"


def test_finished_auctions_listed_newest_first(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    ids = []
    for _ in range(2):
        a = _create_auction(client, seller, create_item(client, seller)["id"]).json()
        _expire(db_session, a["id"])
        ids.append(a["id"])
    db_session.expire_all()
    newer = db_session.get(Auction, ids[1])
    assert newer is not None
    newer.end_time = datetime.now(UTC) - timedelta(seconds=10)
    db_session.commit()
    close_due_auctions(db_session)

    listed = client.get(f"/api/v1/auctions?status=ended&seller_id={seller.id}").json()
    assert [a["id"] for a in listed] == [ids[1], ids[0]]


def test_buy_now_sets_end_time_to_purchase_time(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], buy_now_price="5000").json()

    body = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers).json()
    assert datetime.fromisoformat(body["end_time"]) <= datetime.now(UTC)
    assert body["original_end_time"] == auction["original_end_time"]


# --- Integratsiya: qo'shimcha chekka holatlar ------------------------------------


def test_buy_now_rejected_after_end_time_before_closer(
    client: TestClient, db_session: Session
) -> None:
    """Muddat o'tgan, lekin closer hali yopmagan lot buy-now orqali sotilmaydi."""
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], buy_now_price="5000").json()
    _expire(db_session, auction["id"])

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 409
    assert db_session.scalar(select(Deal).where(Deal.auction_id == auction["id"])) is None


def test_buy_now_rejected_before_start_time(client: TestClient, db_session: Session) -> None:
    """Bid bilan bir xil vaqt oynasi: boshlanmagan auksion sotilmaydi."""
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(client, seller, item["id"], buy_now_price="5000").json()
    db_session.expire_all()
    stored = db_session.get(Auction, auction["id"])
    assert stored is not None
    stored.start_time = datetime.now(UTC) + timedelta(hours=1)
    db_session.commit()

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(Auction, auction["id"]).status == AuctionStatus.ACTIVE


def test_relist_copies_image_records(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    db_session.add_all(
        [
            ItemImage(item_id=item["id"], image_url="/uploads/a.jpg", is_primary=True),
            ItemImage(item_id=item["id"], image_url="/uploads/b.jpg", is_primary=False),
        ]
    )
    db_session.commit()
    auction = _create_auction(client, seller, item["id"]).json()
    _expire(db_session, auction["id"])
    close_due_auctions(db_session)

    new_auction = _relist(client, seller, auction["id"]).json()
    new_item = client.get(f"/api/v1/items/{new_auction['item_id']}").json()
    images = {(i["image_url"], i["is_primary"]) for i in new_item["item_images"]}
    assert images == {("/uploads/a.jpg", True), ("/uploads/b.jpg", False)}


# --- Option B: buy-now rezerv narxga yetguncha ochiq -----------------------------


def test_buy_now_stays_open_below_reserve_and_outbids_existing_bids(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(
        client, seller, item["id"], reserve_price="5000", buy_now_price="8000"
    ).json()

    first = create_bid(client, bidder, auction["id"], amount="1100")
    state = client.get(f"/api/v1/auctions/{auction['id']}").json()
    assert state["reserve_met"] is False
    assert state["buy_now_available"] is True  # bid bor, lekin rezervga yetilmagan

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ended"
    assert body["winner_id"] == buyer.id
    assert body["current_price"] == "8000"

    deal = db_session.scalar(select(Deal).where(Deal.auction_id == auction["id"]))
    assert deal is not None and deal.buyer_id == buyer.id and deal.final_price == 8000

    db_session.expire_all()
    assert db_session.get(Bid, first["id"]).status == BidStatus.OUTBID
    outbid_note = db_session.scalar(
        select(Notification).where(
            Notification.user_id == bidder.id, Notification.type == NotificationType.OUTBID
        )
    )
    assert outbid_note is not None


def test_buy_now_closes_once_reserve_is_met(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(
        client, seller, item["id"], reserve_price="5000", buy_now_price="8000"
    ).json()

    create_bid(client, bidder, auction["id"], amount="5000")
    state = client.get(f"/api/v1/auctions/{auction['id']}").json()
    assert state["reserve_met"] is True
    assert state["buy_now_available"] is False

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 409
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "active"


def test_buy_now_respects_hidden_proxy_max_covering_reserve(
    client: TestClient, db_session: Session
) -> None:
    """Ko'rinadigan narx rezervdan past, lekin yetakchining max'i rezervni qoplagan:
    u rezerv narxida olishga allaqachon rozi — buy-now uni chetlab o'tmaydi.
    Javob umumiy (max qiymati oshkor bo'lmaydi)."""
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(
        client, seller, item["id"], reserve_price="5000", buy_now_price="8000"
    ).json()

    bid = client.post(
        f"/api/v1/auctions/{auction['id']}/bids",
        headers=bidder.headers,
        json={"amount": "1100", "max_amount": "6000"},
    )
    assert bid.status_code == 201, bid.text
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["current_price"] == "1100"

    response = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert response.status_code == 409
    assert "6000" not in response.text
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "active"
    assert db_session.scalar(select(Deal).where(Deal.auction_id == auction["id"])) is None


def test_buy_now_still_allows_later_bids_below_reserve(
    client: TestClient, db_session: Session
) -> None:
    """Buy-now ochiq turgan paytda oddiy bid ham qabul qilinadi (Option B — raqobat to'smaydi)."""
    seller = create_user(client, db_session, email="seller@example.com")
    a = create_user(client, db_session, email="a@example.com")
    b = create_user(client, db_session, email="b@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = _create_auction(
        client, seller, item["id"], reserve_price="5000", buy_now_price="8000"
    ).json()
    create_bid(client, a, auction["id"], amount="1100")
    create_bid(client, b, auction["id"], amount="1300")
    state = client.get(f"/api/v1/auctions/{auction['id']}").json()
    assert state["bid_count"] == 2
    assert state["buy_now_available"] is True
