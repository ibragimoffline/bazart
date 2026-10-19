"""Faza E2.12: kelishuv bildirishnomalari.

Tekshiruvlar matnga emas, TUR va `deal_id` ga tayanadi — so'zlar o'zgarsa testlar buzilmaydi.
Kafolatlar: har kelishuvga aniq bir juftlik "tuzildi"; matn va payload'da telefon/Telegram
yo'q; xabar kelishuv tranzaksiyasida (bekor bo'lsa — yo'q); avto-tasdiq qayta ishlasa ham
"yakunlandi" takrorlanmaydi.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deal import Deal
from app.models.enums import DealStatus, NotificationType
from app.models.notification import Notification
from app.models.user import User
from app.services.deal_service import DealService, contact_notice
from tests.conftest import create_auction, create_bid, create_item, create_user


def _notes(db_session: Session, user_id: int, type_: NotificationType) -> list[Notification]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(Notification).where(Notification.user_id == user_id, Notification.type == type_)
        )
    )


def _auction_deal(client: TestClient, db_session: Session):
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    client.patch("/api/v1/users/me", headers=seller.headers, json={"telegram_username": "shina_uz"})
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    create_bid(client, buyer, auction["id"], amount="1100")
    client.post(f"/api/v1/auctions/{auction['id']}/close", headers=seller.headers)
    deal = client.get("/api/v1/deals/buyer", headers=buyer.headers).json()[0]
    return deal, seller, buyer


def _offer_listing(client: TestClient, seller):
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
    return item


def test_auction_deal_notifies_each_side_once_without_contacts(
    client: TestClient, db_session: Session
) -> None:
    deal, seller, buyer = _auction_deal(client, db_session)
    won = _notes(db_session, buyer.id, NotificationType.WON)
    sold = _notes(db_session, seller.id, NotificationType.SOLD)
    assert len(won) == 1 and len(sold) == 1
    assert won[0].payload["deal_id"] == deal["id"] == sold[0].payload["deal_id"]

    secrets = {
        db_session.get(User, seller.id).phone,
        db_session.get(User, buyer.id).phone,
        "shina_uz",
    }
    everything = db_session.scalars(select(Notification)).all()
    for note in everything:
        blob = f"{note.title} {note.body} {note.payload}"
        assert not any(secret in blob for secret in secrets), blob


def test_offer_deal_notifies_both_with_deal_id(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = _offer_listing(client, seller)
    offer = client.post(
        f"/api/v1/items/{item['id']}/offers",
        headers=buyer.headers,
        json={"quantity": 2, "unit_price": "450000"},
    ).json()
    deal_id = client.post(f"/api/v1/offers/{offer['id']}/accept", headers=seller.headers).json()[
        "deal_id"
    ]
    for user in (buyer, seller):
        notes = _notes(db_session, user.id, NotificationType.OFFER_ACCEPTED)
        assert [n.payload["deal_id"] for n in notes] == [deal_id]


def test_failed_deal_transaction_leaves_no_notification(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kelishuv yaratilgach tranzaksiya yiqilsa — kelishuv ham, xabar ham yo'q."""
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = _offer_listing(client, seller)
    offer = client.post(
        f"/api/v1/items/{item['id']}/offers",
        headers=buyer.headers,
        json={"quantity": 1, "unit_price": "450000"},
    ).json()
    original = DealService.create_for_offer

    def explode(self, offer):
        original(self, offer)
        raise RuntimeError("tranzaksiya oxirida xato")

    monkeypatch.setattr(DealService, "create_for_offer", explode)
    with pytest.raises(RuntimeError):
        client.post(f"/api/v1/offers/{offer['id']}/accept", headers=seller.headers)

    db_session.expire_all()
    assert db_session.scalars(select(Deal)).all() == []
    assert _notes(db_session, buyer.id, NotificationType.OFFER_ACCEPTED) == []


def test_marked_sold_tells_buyer_about_72_hours(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer = _auction_deal(client, db_session)
    client.post(f"/api/v1/deals/{deal['id']}/complete", headers=seller.headers)
    notes = _notes(db_session, buyer.id, NotificationType.DEAL_MARKED_SOLD)
    assert len(notes) == 1
    assert notes[0].payload["deal_id"] == deal["id"]
    assert notes[0].payload["auto_confirm_hours"] == settings.deal_auto_confirm_hours
    assert str(settings.deal_auto_confirm_hours) in notes[0].body
    # Ikkinchi bosish yangi xabar bermaydi.
    client.post(f"/api/v1/deals/{deal['id']}/complete", headers=seller.headers)
    assert len(_notes(db_session, buyer.id, NotificationType.DEAL_MARKED_SOLD)) == 1


def test_cancelled_goes_to_other_side_with_listed_reason(
    client: TestClient, db_session: Session
) -> None:
    deal, seller, buyer = _auction_deal(client, db_session)
    row = db_session.get(Deal, deal["id"])
    row.contacts_revealed_at = datetime.now(UTC) - timedelta(hours=49)
    db_session.commit()
    client.post(
        f"/api/v1/deals/{deal['id']}/cancel", headers=seller.headers, json={"reason": "no_response"}
    )
    to_buyer = _notes(db_session, buyer.id, NotificationType.DEAL_CANCELLED)
    assert len(to_buyer) == 1
    assert to_buyer[0].payload == {
        "deal_id": deal["id"],
        "item_id": deal["item_id"],
        "auction_id": deal["auction_id"],
        "reason": "no_response",
    }
    # Betaraf matn: xaridorni ayblamaydi.
    assert "javob bermadi" not in to_buyer[0].body
    assert _notes(db_session, seller.id, NotificationType.DEAL_CANCELLED) == []


def test_completed_once_even_if_auto_confirm_reruns(
    client: TestClient, db_session: Session
) -> None:
    deal, seller, buyer = _auction_deal(client, db_session)
    client.post(f"/api/v1/deals/{deal['id']}/complete", headers=seller.headers)
    row = db_session.get(Deal, deal["id"])
    row.seller_marked_sold_at = datetime.now(UTC) - timedelta(hours=73)
    db_session.commit()

    assert DealService(db_session).auto_confirm_due() == 1
    assert DealService(db_session).auto_confirm_due() == 0
    for user in (buyer, seller):
        notes = _notes(db_session, user.id, NotificationType.DEAL_COMPLETED)
        assert len(notes) == 1
        assert notes[0].payload["auto"] is True


def test_manual_completion_notifies_both(client: TestClient, db_session: Session) -> None:
    deal, seller, buyer = _auction_deal(client, db_session)
    client.post(f"/api/v1/deals/{deal['id']}/confirm", headers=buyer.headers)
    client.post(f"/api/v1/deals/{deal['id']}/complete", headers=seller.headers)
    for user in (buyer, seller):
        notes = _notes(db_session, user.id, NotificationType.DEAL_COMPLETED)
        assert [n.payload["deal_id"] for n in notes] == [deal["id"]]
    # Xaridor tasdiqlagan bo'lsa "Sotildi" alohida xabar bermaydi — darhol yakunlandi.
    assert _notes(db_session, buyer.id, NotificationType.DEAL_MARKED_SOLD) == []


def test_contact_notice_depends_on_status() -> None:
    assert "Kontaktlar ochildi" in contact_notice(Deal(status=DealStatus.AGREED))
    assert "Kontaktlar" not in contact_notice(Deal(status=DealStatus.CANCELLED))
