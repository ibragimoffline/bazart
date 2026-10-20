import itertools
import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db import base  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.models.base import Base
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository

# Test to'plami "test" muhitida ishlaydi: rate
# limiting o'chiq (aks holda ko'p marta login/bid qiluvchi testlar 429 olardi).
# Muhit-bog'liq xatti-harakatni sinovchi testlar (masalan prod bloklari)
# o'z Settings nusxasini yoki monkeypatch ishlatadi.
settings.environment = "test"
# Dinamik (darajali) minimal qadam poli test muhitida o'chiriladi: mavjud
# test korpusi kichik tiyin summalar ishlatadi (real narxlar emas). Jadval
# mantig'i alohida test_tiered_increment.py da (pure-function + floor yoqilgan
# integratsiya testi) tekshiriladi.
settings.tiered_bid_increment_enabled = False

# REAL Postgres — SQLite EMAS.
#
# Ilgari bu yerda sqlite+pysqlite:///:memory: turardi. SQLite `FOR UPDATE`,
# native ENUM, BIGINT/Numeric semantikasi va tranzaksiya izolyatsiyasida
# Postgres'dan farq qiladi. Pul va auksion logikasini SQLite'da sinash
# yolg'on ishonch beradi: qulf yozilmagan bo'lsa ham test yashil bo'ladi.
#
# Baza ko'tarilgan bo'lishi kerak: docker compose up -d db
#
# Port 5433 (5432 emas): mahalliy o'rnatilgan Postgres 5432 ni egallab
# turishi mumkin, u holda testlar jimgina noto'g'ri serverga ulanadi.
# CI'da TEST_DATABASE_URL env orqali beriladi.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/bazart_test",
)
TEST_PASSWORD = "Password1"

# Faza E2.1: bid, taklif, e'lon va xarid uchun telefon tasdig'i majburiy. Mavjud test korpusi
# foydalanuvchilarni API orqali ro'yxatdan o'tkazadi (OTP'siz), shuning uchun har yangi
# foydalanuvchiga zaxira oralig'idan (+998 00 ...) noyob tasdiqlangan raqam beriladi. Talab
# o'zi O'CHIRILMAYDI — u har testda ishlaydi. Tasdiqlanmagan holatni sinovchi testlar
# `unverified_phones` fixture'ini ishlatadi.
#
# Holat `User` klassida saqlanadi: ba'zi testlar `conftest`, ba'zilari `tests.conftest` deb
# import qiladi — modul ikki marta yuklansa ham listener va bayroq bitta bo'lib qoladi.
_STATE_ATTR = "_test_auto_verify_phones"
if _STATE_ATTR not in User.__dict__:
    _state = {"on": True, "seq": itertools.count(1)}

    def _auto_verify_test_phone(mapper, connection, target: User) -> None:  # noqa: ARG001
        if _state["on"] and target.phone is None and target.phone_verified_at is None:
            target.phone = f"+99800{next(_state['seq']):07d}"
            target.phone_verified_at = datetime.now(UTC)

    setattr(User, _STATE_ATTR, _state)
    event.listen(User, "before_insert", _auto_verify_test_phone)
_AUTO_VERIFY_PHONES: dict = User.__dict__[_STATE_ATTR]


@pytest.fixture
def unverified_phones() -> Generator[None]:
    """Shu test davomida yangi foydalanuvchilar telefonsiz va tasdiqlanmagan yaratiladi."""
    _AUTO_VERIFY_PHONES["on"] = False
    try:
        yield
    finally:
        _AUTO_VERIFY_PHONES["on"] = True


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    email: str
    password: str
    access_token: str
    refresh_token: str
    headers: dict[str, str]


def _ensure_test_database_exists(url: str) -> None:
    """Test bazasi yo'q bo'lsa yaratadi.

    `postgres` xizmat bazasiga ulanib CREATE DATABASE qiladi — shu sababli
    AUTOCOMMIT kerak (CREATE DATABASE tranzaksiya ichida ishlamaydi).
    """
    target = make_url(url)
    admin_engine = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.database},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin_engine.dispose()


def _reset_test_schema(engine: Engine) -> None:
    """Test bazasi sxemasini to'liq tozalaydi (DROP SCHEMA public CASCADE).

    `metadata.drop_all` faqat JORIY modellardagi jadvallarni biladi: model olib
    tashlansa (masalan narx ko'rsatkichi), uning eski jadvali `users`ga FK bilan bog'liq
    qolib, drop_all'ni yiqitadi va barcha testlar ERROR beradi. Shuning uchun sxema
    butunlay qayta yaratiladi. Himoya: faqat nomi `_test` bilan tugaydigan baza.
    """
    database = engine.url.database or ""
    if not database.endswith("_test"):
        raise RuntimeError(f"Xavfsizlik: '{database}' test bazasi emas — sxema tozalanmaydi")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    """Sessiya davomida bitta engine + sxema bir marta quriladi.

    Har test uchun create_all/drop_all qilish Postgres'da sekin (native
    ENUM turlari qayta yaratiladi). O'rniga sxema bir marta quriladi,
    tozalash TRUNCATE bilan qilinadi.
    """
    try:
        _ensure_test_database_exists(TEST_DATABASE_URL)
    except OSError as exc:  # ulanib bo'lmadi
        pytest.exit(
            f"Test Postgres'iga ulanib bo'lmadi ({TEST_DATABASE_URL}): {exc}\n"
            "Bazani ko'taring: docker compose up -d db",
            returncode=1,
        )

    engine = create_engine(TEST_DATABASE_URL)
    _reset_test_schema(engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session]:
    """Har test toza bazadan boshlanadi.

    TRUNCATE ... RESTART IDENTITY CASCADE — ID'lar 1 dan boshlanadi,
    ya'ni testlar bir-biriga ID orqali ta'sir qilmaydi.
    """
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    if tables:
        with db_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    def override_get_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def register_user(
    client: TestClient,
    *,
    email: str,
    password: str = TEST_PASSWORD,
    full_name: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name or email.split("@")[0],
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(
    client: TestClient,
    *,
    email: str,
    password: str = TEST_PASSWORD,
) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    # Refresh token tanada emas, HttpOnly cookie'da — testlar uchun shu yerdan olinadi.
    return {**response.json(), "refresh_token": response.cookies[settings.refresh_cookie_name]}


def create_user(
    client: TestClient,
    db_session: Session,
    *,
    email: str,
    role: UserRole = UserRole.USER,
    password: str = TEST_PASSWORD,
) -> AuthenticatedUser:
    registered_user = register_user(client, email=email, password=password)
    if role != UserRole.USER:
        user = UserRepository(db_session).get_by_email(email)
        assert user is not None
        UserRepository(db_session).set_role(user, role)

    token_payload = login_user(client, email=email, password=password)
    return AuthenticatedUser(
        id=registered_user["id"],
        email=email,
        password=password,
        access_token=token_payload["access_token"],
        refresh_token=token_payload["refresh_token"],
        headers=auth_headers(token_payload["access_token"]),
    )


def create_item(
    client: TestClient,
    seller: AuthenticatedUser,
    *,
    title: str = "Test item",
    starting_price: str = "1000",
    category_id: int | None = None,
) -> dict:
    payload = {
        "title": title,
        "condition": "used",
        "starting_price": starting_price,
        "defects": "yo'q",
    }
    if category_id is not None:
        payload["category_id"] = category_id
    response = client.post("/api/v1/items", headers=seller.headers, json=payload)
    assert response.status_code == 201
    return response.json()


def create_auction(
    client: TestClient,
    seller: AuthenticatedUser,
    item_id: int,
    *,
    start_delta: timedelta = -timedelta(minutes=1),
    end_delta: timedelta = timedelta(days=1),
    minimum_bid_increment: str = "100",
    reserve_price: str | None = None,
) -> dict:
    now = datetime.now(UTC)
    payload = {
        "item_id": item_id,
        "start_time": (now + start_delta).isoformat(),
        "end_time": (now + end_delta).isoformat(),
        "minimum_bid_increment": minimum_bid_increment,
    }
    if reserve_price is not None:
        payload["reserve_price"] = reserve_price
    response = client.post("/api/v1/auctions", headers=seller.headers, json=payload)
    assert response.status_code == 201
    return response.json()


def create_bid(
    client: TestClient,
    bidder: AuthenticatedUser,
    auction_id: int,
    *,
    amount: str | int = "1100",
) -> dict:
    response = client.post(
        f"/api/v1/bids/{auction_id}",
        headers=bidder.headers,
        json={"amount": str(amount)},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def test_user(client: TestClient, db_session: Session) -> AuthenticatedUser:
    return create_user(client, db_session, email="user@example.com")


@pytest.fixture
def test_seller(client: TestClient, db_session: Session) -> AuthenticatedUser:
    return create_user(client, db_session, email="seller@example.com", role=UserRole.SELLER)


@pytest.fixture
def test_admin(client: TestClient, db_session: Session) -> AuthenticatedUser:
    return create_user(client, db_session, email="admin@example.com", role=UserRole.ADMIN)
