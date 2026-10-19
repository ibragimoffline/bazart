"""Faza E2.5: kelishuvda kontaktlar va IDOR (docs/DEALS.md §4).

Ikkinchi tomonning tasdiqlangan telefoni va Telegram nomi faqat kelishuv ishtirokchisiga
ochiladi. Begona — 404, admin kelishuvni ko'radi, lekin kontaktsiz. Ochilgan kontakt
kelishuv bekor bo'lsa ham yashirilmaydi. Ro'yxatlar, bidlar va takliflarda raqam yo'q.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    AuthenticatedUser,
    create_auction,
    create_bid,
    create_item,
    create_user,
)


def _phone(db_session: Session, user: AuthenticatedUser) -> str:
    return db_session.get(User, user.id).phone


def _deal(client: TestClient, db_session: Session):
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    client.patch(
        "/api/v1/users/me", headers=seller.headers, json={"telegram_username": "@shina_uz"}
    )
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    create_bid(client, buyer, auction["id"], amount="1100")
    client.post(f"/api/v1/auctions/{auction['id']}/close", headers=seller.headers)
    deal = client.get("/api/v1/deals/buyer", headers=buyer.headers).json()[0]
    return deal, seller, buyer, auction


def test_participants_see_each_others_contacts(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer, _ = _deal(client, db_session)

    as_buyer = client.get(f"/api/v1/deals/{deal['id']}", headers=buyer.headers).json()
    assert as_buyer["counterparty"] == {
        "user_id": seller.id,
        "full_name": "seller",
        "phone": _phone(db_session, seller),
        "telegram_username": "shina_uz",
    }

    as_seller = client.get(f"/api/v1/deals/{deal['id']}", headers=seller.headers).json()
    assert as_seller["counterparty"]["user_id"] == buyer.id
    assert as_seller["counterparty"]["phone"] == _phone(db_session, buyer)


def test_stranger_gets_404_and_admin_sees_no_contacts(
    client: TestClient, db_session: Session
) -> None:
    deal, _seller, _buyer, _ = _deal(client, db_session)
    stranger = create_user(client, db_session, email="stranger@example.com")
    assert client.get(f"/api/v1/deals/{deal['id']}", headers=stranger.headers).status_code == 404
    assert client.get("/api/v1/deals/999999", headers=stranger.headers).status_code == 404

    admin = create_user(client, db_session, email="admin@example.com", role=UserRole.ADMIN)
    as_admin = client.get(f"/api/v1/deals/{deal['id']}", headers=admin.headers)
    assert as_admin.status_code == 200
    assert as_admin.json()["counterparty"] is None


def test_lists_bids_and_history_never_carry_phone(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer, auction = _deal(client, db_session)
    phones = {_phone(db_session, seller), _phone(db_session, buyer)}
    responses = [
        client.get("/api/v1/deals/buyer", headers=buyer.headers),
        client.get("/api/v1/deals/seller", headers=seller.headers),
        client.get(f"/api/v1/auctions/{auction['id']}/bids", headers=buyer.headers),
        client.get(f"/api/v1/auctions/{auction['id']}"),
    ]
    for response in responses:
        assert response.status_code == 200, response.text
        assert not any(phone in response.text for phone in phones), response.request.url


def test_unverified_phone_is_not_revealed(client: TestClient, db_session: Session) -> None:
    """Raqam kelishuvdan keyin o'zgartirilsa tasdiq bekor — tasdiqlanmagan raqam ochilmaydi."""
    deal, seller, buyer, _ = _deal(client, db_session)
    client.patch("/api/v1/users/me", headers=seller.headers, json={"phone": "+998935550000"})
    counterparty = client.get(f"/api/v1/deals/{deal['id']}", headers=buyer.headers).json()[
        "counterparty"
    ]
    assert counterparty["phone"] is None
    assert counterparty["telegram_username"] == "shina_uz"


def test_contacts_stay_visible_after_cancel(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer, _ = _deal(client, db_session)
    client.post(
        f"/api/v1/deals/{deal['id']}/cancel", headers=buyer.headers, json={"reason": "changed_mind"}
    )
    body = client.get(f"/api/v1/deals/{deal['id']}", headers=buyer.headers).json()
    assert body["status"] == "cancelled"
    assert body["counterparty"]["phone"] == _phone(db_session, seller)


def test_telegram_username_is_validated(client: TestClient, db_session: Session) -> None:
    user = create_user(client, db_session, email="u@example.com")
    ok = client.patch(
        "/api/v1/users/me", headers=user.headers, json={"telegram_username": "t.me/Bazart_uz"}
    )
    assert ok.json()["telegram_username"] == "Bazart_uz"
    bad = client.patch("/api/v1/users/me", headers=user.headers, json={"telegram_username": "a b"})
    assert bad.status_code == 422
