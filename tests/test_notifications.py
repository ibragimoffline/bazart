"""In-app bildirishnoma testlari.

Bildirishnomalar to'g'ridan-to'g'ri NotificationService orqali yaratiladi
(event hook'lar hali ulanmagan), keyin HTTP endpoint'lar tekshiriladi:
egalik izolyatsiyasi, o'qilmaganlar soni, bittalab va ommaviy o'qish.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.services.notification_service import NotificationService
from tests.conftest import create_user


def _seed(db_session: Session, user_id: int, type: NotificationType, title: str) -> None:
    NotificationService(db_session).create(user_id=user_id, type=type, title=title)


def test_list_returns_only_mine_newest_first(client: TestClient, db_session: Session) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    other = create_user(client, db_session, email="other@example.com")

    _seed(db_session, owner.id, NotificationType.OUTBID, "Birinchi")
    _seed(db_session, owner.id, NotificationType.WON, "Ikkinchi")
    _seed(db_session, other.id, NotificationType.SOLD, "Begonaniki")
    db_session.commit()

    response = client.get("/api/v1/notifications", headers=owner.headers)
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2  # begonaniki ko'rinmaydi
    # created_at desc — oxirgi yaratilgan birinchi
    assert data[0]["title"] == "Ikkinchi"
    assert data[1]["title"] == "Birinchi"
    assert all(item["is_read"] is False for item in data)


def test_unread_count(client: TestClient, db_session: Session) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    _seed(db_session, owner.id, NotificationType.OUTBID, "A")
    _seed(db_session, owner.id, NotificationType.OFFER_RECEIVED, "B")
    _seed(db_session, owner.id, NotificationType.ENDING_SOON, "C")
    db_session.commit()

    response = client.get("/api/v1/notifications/unread-count", headers=owner.headers)
    assert response.status_code == 200
    assert response.json() == {"count": 3}


def test_only_unread_filter(client: TestClient, db_session: Session) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    n1 = NotificationService(db_session).create(
        user_id=owner.id, type=NotificationType.OUTBID, title="A"
    )
    _seed(db_session, owner.id, NotificationType.WON, "B")
    db_session.commit()

    # Bittasini o'qilgan qilamiz
    client.post(f"/api/v1/notifications/{n1.id}/read", headers=owner.headers)

    response = client.get(
        "/api/v1/notifications", headers=owner.headers, params={"only_unread": True}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "B"


def test_mark_read_flips_flag_and_decrements_count(client: TestClient, db_session: Session) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    target = NotificationService(db_session).create(
        user_id=owner.id, type=NotificationType.OUTBID, title="O'qiladi"
    )
    _seed(db_session, owner.id, NotificationType.WON, "Qoladi")
    db_session.commit()

    before = client.get("/api/v1/notifications/unread-count", headers=owner.headers).json()["count"]
    assert before == 2

    read = client.post(f"/api/v1/notifications/{target.id}/read", headers=owner.headers)
    assert read.status_code == 200
    payload = read.json()
    assert payload["is_read"] is True
    assert payload["read_at"] is not None

    after = client.get("/api/v1/notifications/unread-count", headers=owner.headers).json()["count"]
    assert after == 1


def test_cannot_read_others_notification(client: TestClient, db_session: Session) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    attacker = create_user(client, db_session, email="attacker@example.com")
    victim_notif = NotificationService(db_session).create(
        user_id=owner.id, type=NotificationType.SOLD, title="Maxfiy"
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/notifications/{victim_notif.id}/read", headers=attacker.headers
    )
    assert response.status_code in (403, 404)

    # Egaas bildirishnoma hali o'qilmagan bo'lib qolishi kerak
    still = client.get("/api/v1/notifications/unread-count", headers=owner.headers).json()["count"]
    assert still == 1


def test_read_all_marks_everything(client: TestClient, db_session: Session) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    other = create_user(client, db_session, email="other@example.com")
    for i in range(3):
        _seed(db_session, owner.id, NotificationType.OUTBID, f"N{i}")
    _seed(db_session, other.id, NotificationType.WON, "Begonaniki")
    db_session.commit()

    response = client.post("/api/v1/notifications/read-all", headers=owner.headers)
    assert response.status_code == 200
    assert response.json() == {"count": 3}  # faqat o'zining 3 tasi

    assert (
        client.get("/api/v1/notifications/unread-count", headers=owner.headers).json()["count"] == 0
    )
    # Begonaning bildirishnomasiga tegilmagan
    assert (
        client.get("/api/v1/notifications/unread-count", headers=other.headers).json()["count"] == 1
    )
