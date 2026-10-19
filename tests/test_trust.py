"""Faza E2.9: ishonch hisoblagichlari va bekor qilish cheklovi (docs/DEALS.md §8)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.user import User
from app.services.trust_service import TRADING_RESTRICTED, TrustService
from tests.conftest import AuthenticatedUser, create_auction, create_bid, create_item, create_user


def _deal(client: TestClient, seller: AuthenticatedUser, buyer: AuthenticatedUser, n: int) -> int:
    item = create_item(client, seller, title=f"Lot {n}")
    auction = create_auction(client, seller, item["id"])
    create_bid(client, buyer, auction["id"], amount="1100")
    client.post(f"/api/v1/auctions/{auction['id']}/close", headers=seller.headers)
    return next(
        d["id"]
        for d in client.get("/api/v1/deals/buyer", headers=buyer.headers).json()
        if d["auction_id"] == auction["id"]
    )


def _cancel(client: TestClient, user: AuthenticatedUser, deal_id: int, reason: str) -> None:
    response = client.post(
        f"/api/v1/deals/{deal_id}/cancel", headers=user.headers, json={"reason": reason}
    )
    assert response.status_code == 200, response.text


def _age(db_session: Session, deal_id: int, days: float) -> None:
    row = db_session.get(Deal, deal_id)
    row.cancelled_at = datetime.now(UTC) - timedelta(days=days)
    db_session.commit()


def _parties(client: TestClient, db_session: Session):
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    return seller, buyer


def test_counters_follow_fault_not_canceller(client: TestClient, db_session: Session) -> None:
    seller, buyer = _parties(client, db_session)
    done = _deal(client, seller, buyer, 1)
    client.post(f"/api/v1/deals/{done}/complete", headers=seller.headers)
    client.post(f"/api/v1/deals/{done}/confirm", headers=buyer.headers)
    # Xaridor bekor qildi, lekin mahsulot e'londagidek emas -> aybdor sotuvchi.
    _cancel(client, buyer, _deal(client, seller, buyer, 2), "not_as_described")
    _cancel(client, buyer, _deal(client, seller, buyer, 3), "changed_mind")

    s_seller = TrustService(db_session).stats(seller.id)
    s_buyer = TrustService(db_session).stats(buyer.id)
    assert (s_seller.deals_completed, s_seller.cancelled_as_seller) == (1, 1)
    assert (s_buyer.deals_completed, s_buyer.cancelled_as_buyer) == (1, 1)
    assert s_seller.cancelled_as_buyer == 0 and s_buyer.cancelled_as_seller == 0


def test_public_profile_has_counters_but_no_contacts(
    client: TestClient, db_session: Session
) -> None:
    seller, buyer = _parties(client, db_session)
    _cancel(client, buyer, _deal(client, seller, buyer, 1), "changed_mind")
    response = client.get(f"/api/v1/users/{buyer.id}/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["cancelled_as_buyer"] == 1
    assert body["deals_completed"] == 0
    phone = db_session.get(User, buyer.id).phone
    assert phone not in response.text
    assert buyer.email not in response.text
    assert "telegram" not in response.text
    assert client.get("/api/v1/users/999999/profile").status_code == 404


def test_three_faults_in_30_days_restrict_bids_offers_and_buy_now(
    client: TestClient, db_session: Session
) -> None:
    seller, buyer = _parties(client, db_session)
    for n in range(3):
        _cancel(client, buyer, _deal(client, seller, buyer, n), "changed_mind")

    item = create_item(client, seller, title="Yangi lot")
    auction = create_auction(client, seller, item["id"])
    bid = client.post(
        f"/api/v1/bids/{auction['id']}", headers=buyer.headers, json={"amount": "1100"}
    )
    assert bid.status_code == 403
    assert bid.json()["detail"] == TRADING_RESTRICTED
    buy = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert buy.json()["detail"] == TRADING_RESTRICTED
    offer = client.post(
        f"/api/v1/items/{item['id']}/offers",
        headers=buyer.headers,
        json={"quantity": 1, "unit_price": "1000"},
    )
    assert offer.json()["detail"] == TRADING_RESTRICTED

    # E'lon joylash cheklanmaydi; aybdor bo'lmagan sotuvchi ham savdo qila oladi.
    own = client.post(
        "/api/v1/items",
        headers=buyer.headers,
        json={"title": "Velosiped", "condition": "used", "starting_price": "90000000"},
    )
    assert own.status_code == 201
    assert TrustService(db_session).restricted_until(seller.id) is None


def test_faults_spread_beyond_window_do_not_restrict(
    client: TestClient, db_session: Session
) -> None:
    seller, buyer = _parties(client, db_session)
    for n, days_ago in enumerate((40, 20, 1)):
        deal_id = _deal(client, seller, buyer, n)
        _cancel(client, buyer, deal_id, "changed_mind")
        _age(db_session, deal_id, days_ago)
    assert TrustService(db_session).restricted_until(buyer.id) is None


def test_restriction_expires_after_ban_days(client: TestClient, db_session: Session) -> None:
    seller, buyer = _parties(client, db_session)
    for n, days_ago in enumerate((20, 18, 15)):
        deal_id = _deal(client, seller, buyer, n)
        _cancel(client, buyer, deal_id, "changed_mind")
        _age(db_session, deal_id, days_ago)
    # Uchinchisi 15 kun oldin -> taqiq 1 kun oldin tugagan.
    assert TrustService(db_session).restricted_until(buyer.id) is None

    _age(db_session, deal_id, 10)
    until = TrustService(db_session).restricted_until(buyer.id)
    assert until is not None and until > datetime.now(UTC)
