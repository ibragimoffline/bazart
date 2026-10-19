"""Faza E2.4: kelishuvning yagona kirish nuqtasi — `DealService.create_deal`.

E5 komissiyasi va kelishuv bildirishnomalari shu funksiyaga ulanadi: agar biror oqim
kelishuvni boshqa yo'l bilan yaratsa, komissiya jimgina olinmay qoladi. Ikki qatlam:
statik (kodda `Deal(...)` faqat bitta joyda) va dinamik (asosiy oqimlar shu nuqtadan o'tadi).
"""

import ast
import pathlib
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.deal_service import DealService
from tests.conftest import create_auction, create_bid, create_item, create_user

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def test_deal_is_constructed_only_in_create_deal() -> None:
    hits: list[str] = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(fn):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "Deal"
                ):
                    hits.append(f"{path.relative_to(APP).as_posix()}:{fn.name}")
    assert sorted(set(hits)) == ["services/deal_service.py:create_deal"]


def _spy(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    original = DealService.create_deal

    def spy(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(DealService, "create_deal", spy)
    return calls


def test_offer_accept_goes_through_create_deal(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    calls = _spy(monkeypatch)
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    item = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json={
            "title": "Qishki shina 205/55 R16",
            "condition": "new",
            "starting_price": "60000000",
            "quantity": 4,
        },
    ).json()
    published = client.post(
        f"/api/v1/items/{item['id']}/publish",
        headers=seller.headers,
        json={"listing_type": "offer", "duration_days": 3},
    )
    assert published.status_code == 200, published.text
    offer = client.post(
        f"/api/v1/items/{item['id']}/offers",
        headers=buyer.headers,
        json={"quantity": 2, "unit_price": "55000000"},
    ).json()
    accepted = client.post(f"/api/v1/offers/{offer['id']}/accept", headers=seller.headers)
    assert accepted.status_code == 200, accepted.text

    assert len(calls) == 1
    assert calls[0]["offer_id"] == offer["id"]
    assert calls[0]["quantity"] == 2


def test_auction_close_and_buy_now_go_through_create_deal(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    calls = _spy(monkeypatch)
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")

    closed_item = create_item(client, seller)
    closed = create_auction(client, seller, closed_item["id"])
    create_bid(client, buyer, closed["id"], amount="1100")
    assert (
        client.post(f"/api/v1/auctions/{closed['id']}/close", headers=seller.headers).status_code
        == 200
    )

    bn_item = create_item(client, seller, title="Buy now item")
    now = datetime.now(UTC)
    bn = client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": bn_item["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "minimum_bid_increment": "100",
            "buy_now_price": "5000",
        },
    ).json()
    bought = client.post(f"/api/v1/auctions/{bn['id']}/buy-now", headers=buyer.headers)
    assert bought.status_code == 200, bought.text

    assert [c["auction_id"] for c in calls] == [closed["id"], bn["id"]]
