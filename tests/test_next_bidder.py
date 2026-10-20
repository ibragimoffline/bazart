"""Faza E2.10: g'olib javob bermasa — keyingi bidderga 24 soatlik taklif (docs/DEALS.md §6).

Asosiy ketma-ketlik: g'olib javob bermaydi -> sotuvchi kelishuvni bekor qiladi (no_response)
-> keyingi bidderga taklif -> u qabul qiladi -> ikkinchi kelishuv. Kafolatlar:
- bir auksionda bir vaqtda bitta tirik kelishuv (qulf + `uq_deals_auction_active`);
- taklif olgan bidderga ikkinchi marta taklif yo'q, bid tarixi o'zgarmaydi;
- parallel ikki qabuldan faqat bittasi o'tadi; taklif 24 soatda o'z-o'zidan eskiradi;
- ochiq taklif turganda qayta joylash rad etiladi.
"""

import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.auction import Auction
from app.models.bid import Bid
from app.models.deal import Deal
from app.models.next_bidder_offer import NextBidderOffer
from app.models.user import User
from app.services.auction_service import AuctionService
from tests.conftest import create_auction, create_bid, create_item, create_user


def _setup(client: TestClient, db_session: Session, *, reason: str = "no_response", third=False):
    seller = create_user(client, db_session, email="seller@example.com")
    winner = create_user(client, db_session, email="winner@example.com")
    runner = create_user(client, db_session, email="runner@example.com")
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    others = []
    if third:
        others.append(create_user(client, db_session, email="third@example.com"))
        create_bid(client, others[0], auction["id"], amount="1100")
    create_bid(client, runner, auction["id"], amount="1200" if third else "1100")
    create_bid(client, winner, auction["id"], amount="1300")
    client.post(f"/api/v1/auctions/{auction['id']}/close", headers=seller.headers)
    deal = client.get("/api/v1/deals/buyer", headers=winner.headers).json()[0]

    # G'olib 48 soat javob bermadi -> sotuvchi bekor qiladi.
    row = db_session.get(Deal, deal["id"])
    row.contacts_revealed_at = datetime.now(UTC) - timedelta(hours=49)
    db_session.commit()
    cancelled = client.post(
        f"/api/v1/deals/{deal['id']}/cancel", headers=seller.headers, json={"reason": reason}
    )
    assert cancelled.status_code == 200, cancelled.text
    return seller, winner, runner, auction, deal, others


def _offer(client: TestClient, user, deal_id: int):
    return client.post(f"/api/v1/deals/{deal_id}/offer-next-bidder", headers=user.headers)


def _accept(client: TestClient, user, auction_id: int):
    return client.post(f"/api/v1/auctions/{auction_id}/next-offer/accept", headers=user.headers)


def _bid_snapshot(db_session: Session, auction_id: int) -> list[tuple]:
    db_session.expire_all()
    return [
        (b.id, b.bidder_id, b.amount, b.status)
        for b in db_session.scalars(
            select(Bid).where(Bid.auction_id == auction_id).order_by(Bid.id)
        )
    ]


def test_full_sequence_creates_second_deal(client: TestClient, db_session: Session) -> None:
    seller, winner, runner, auction, deal, _ = _setup(client, db_session)
    bids_before = _bid_snapshot(db_session, auction["id"])

    offer = _offer(client, seller, deal["id"])
    assert offer.status_code == 200, offer.text
    assert offer.json()["amount"] == "1100"

    accepted = _accept(client, runner, auction["id"])
    assert accepted.status_code == 200, accepted.text
    second = accepted.json()
    assert (second["buyer_id"], second["unit_price"], second["status"]) == (
        runner.id,
        "1100",
        "agreed",
    )
    assert second["id"] != deal["id"]

    db_session.expire_all()
    row = db_session.get(Auction, auction["id"])
    assert row.winner_id == runner.id
    assert row.active_deal.id == second["id"]
    assert db_session.get(Deal, deal["id"]).status.value == "cancelled"
    # Bid tarixi o'zgarmagan; taklif yozuvi natija bilan saqlangan.
    assert _bid_snapshot(db_session, auction["id"]) == bids_before
    record = db_session.scalar(select(NextBidderOffer))
    assert record.accepted_at is not None and record.deal_id == second["id"]

    # Ikkinchi tirik kelishuv yo'q.
    assert _offer(client, seller, deal["id"]).status_code == 409


def test_offered_bidder_is_never_offered_again(client: TestClient, db_session: Session) -> None:
    seller, _winner, runner, auction, deal, others = _setup(client, db_session, third=True)
    first = _offer(client, seller, deal["id"])
    assert first.json()["amount"] == "1200"  # runner

    record = db_session.scalar(select(NextBidderOffer))
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    second = _offer(client, seller, deal["id"])
    assert second.status_code == 200, second.text
    assert second.json()["amount"] == "1100"  # uchinchi bidder, runner emas
    assert _accept(client, runner, auction["id"]).status_code == 409
    assert _accept(client, others[0], auction["id"]).status_code == 200

    db_session.expire_all()
    offered = db_session.scalars(select(NextBidderOffer.bidder_id)).all()
    assert sorted(offered) == sorted([runner.id, others[0].id])


def test_offer_expires_after_24_hours(client: TestClient, db_session: Session) -> None:
    seller, _winner, runner, auction, deal, _ = _setup(client, db_session)
    _offer(client, seller, deal["id"])
    record = db_session.scalar(select(NextBidderOffer))
    assert record.expires_at - record.offered_at == timedelta(hours=24)

    record.offered_at -= timedelta(hours=24, seconds=1)
    record.expires_at -= timedelta(hours=24, seconds=1)
    db_session.commit()
    late = _accept(client, runner, auction["id"])
    assert late.status_code == 409
    # Boshqa bidder yo'q — sotuvchiga qayta joylash aytiladi.
    again = _offer(client, seller, deal["id"])
    assert again.status_code == 409
    assert "qayta joylang" in again.json()["detail"]


def test_relist_is_rejected_while_offer_is_open(client: TestClient, db_session: Session) -> None:
    seller, *_rest, auction, deal, _ = _setup(client, db_session)
    _offer(client, seller, deal["id"])
    relist = client.post(
        f"/api/v1/auctions/{auction['id']}/relist",
        headers=seller.headers,
        json={"duration_days": 5, "starting_price": "900"},
    )
    assert relist.status_code == 409
    assert relist.json()["detail"] == "Keyingi bidderga ochiq taklif bor"


def test_only_after_no_response(client: TestClient, db_session: Session) -> None:
    seller, *_rest, deal, _ = _setup(client, db_session, reason="changed_mind")
    assert _offer(client, seller, deal["id"]).status_code == 409


def test_only_seller_offers_and_only_offered_bidder_accepts(
    client: TestClient, db_session: Session
) -> None:
    seller, winner, runner, auction, deal, _ = _setup(client, db_session)
    assert _offer(client, runner, deal["id"]).status_code == 404
    _offer(client, seller, deal["id"])
    assert _accept(client, winner, auction["id"]).status_code == 404


def test_parallel_accepts_only_one_succeeds(
    client: TestClient, db_session: Session, db_engine: Engine
) -> None:
    seller, _winner, runner, auction, deal, _ = _setup(client, db_session)
    _offer(client, seller, deal["id"])

    factory = sessionmaker(bind=db_engine)
    barrier = threading.Barrier(2)
    results: list[object] = []

    def run() -> None:
        with factory() as db:
            barrier.wait()
            try:
                results.append(
                    AuctionService(db).accept_next_offer(auction["id"], db.get(User, runner.id))
                )
            except HTTPException as exc:
                results.append(exc.status_code)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(r if isinstance(r, int) else 200 for r in results) == [200, 409]
    db_session.expire_all()
    live = db_session.scalars(
        select(Deal).where(Deal.auction_id == auction["id"], Deal.status != "CANCELLED")
    ).all()
    assert len(live) == 1


@pytest.mark.parametrize("units", [2])
def test_offer_deals_without_auction_are_unaffected(
    client: TestClient, db_session: Session, units: int
) -> None:
    """auction_id NULL bo'lgan taklif kelishuvlari bitta e'londan bir nechta bo'la oladi."""
    seller = create_user(client, db_session, email="seller@example.com")
    item = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json={
            "title": "Qishki shina",
            "condition": "new",
            "starting_price": "500000",
            "quantity": 4,
        },
    ).json()
    client.post(
        f"/api/v1/items/{item['id']}/publish",
        headers=seller.headers,
        json={"listing_type": "offer", "duration_days": 3},
    )
    for n in range(units):
        buyer = create_user(client, db_session, email=f"b{n}@example.com")
        offer = client.post(
            f"/api/v1/items/{item['id']}/offers",
            headers=buyer.headers,
            json={"quantity": 1, "unit_price": "450000"},
        ).json()
        ok = client.post(f"/api/v1/offers/{offer['id']}/accept", headers=seller.headers)
        assert ok.status_code == 200, ok.text
    deals = client.get("/api/v1/deals/seller", headers=seller.headers).json()
    assert len(deals) == units and all(d["auction_id"] is None for d in deals)


def _seller_expiry_notes(db_session: Session, seller_id: int) -> list:
    from app.models.enums import NotificationType
    from app.models.notification import Notification

    db_session.expire_all()
    return [
        n
        for n in db_session.scalars(
            select(Notification).where(
                Notification.user_id == seller_id,
                Notification.type == NotificationType.SECOND_CHANCE,
            )
        )
        if (n.payload or {}).get("expired")
    ]


def test_expiry_job_marks_offer_and_notifies_seller_once(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    seller, _winner, _runner, auction, deal, _ = _setup(client, db_session)
    _offer(client, seller, deal["id"])
    # Muddat hali kelmagan — vazifa tegmaydi.
    assert AuctionService(db_session).expire_next_offers() == 0

    record = db_session.scalar(select(NextBidderOffer))
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    from app.tasks.scheduled import expire_next_offers_task

    monkeypatch.setattr("app.tasks.scheduled.SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    assert expire_next_offers_task() == 1
    assert AuctionService(db_session).expire_next_offers() == 0  # qayta ishlamaydi

    db_session.expire_all()
    assert db_session.scalar(select(NextBidderOffer)).expired_at is not None
    notes = _seller_expiry_notes(db_session, seller.id)
    assert len(notes) == 1
    assert notes[0].payload == {"auction_id": auction["id"], "expired": True}


def test_expiry_job_ignores_accepted_offer(client: TestClient, db_session: Session) -> None:
    seller, _winner, runner, auction, deal, _ = _setup(client, db_session)
    _offer(client, seller, deal["id"])
    _accept(client, runner, auction["id"])
    record = db_session.scalar(select(NextBidderOffer))
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert AuctionService(db_session).expire_next_offers() == 0
    assert _seller_expiry_notes(db_session, seller.id) == []


def test_expiry_job_is_in_beat_schedule() -> None:
    from app.core.celery_app import build_beat_schedule

    tasks = {entry["task"] for entry in build_beat_schedule().values()}
    assert "app.tasks.scheduled.expire_next_offers_task" in tasks
    assert "app.tasks.scheduled.auto_confirm_deals_task" in tasks
