"""Auksion real-time WebSocket endpoint — narx/holat yangilanishlari kanali.

Mijoz `/api/v1/ws/auctions/{auction_id}?token=<JWT>` ga ulanadi va shu auksion
bo'yicha yangilanishlarni oladi. MVP'da endpoint oddiy RELAY: mijozdan kelgan
har qanday JSON xabar shu auksion room'idagi qolgan mijozlarga tarqatiladi.
Bu narx yangilanishini simulyatsiya qilish va testlash uchun yetarli.
Kelajakda broadcast'ni `bid_service` (bid qo'yilganda) ishga tushiradi.

Auth — ulanish uchun yaroqli access JWT MAJBURIY. Brauzer WebSocket handshake'iga
Authorization sarlavhasini qo'ya olmaydi, token URL'da esa proxy/access log'larga
tushadi. Shuning uchun token ULANGANDAN KEYIN birinchi xabarda yuboriladi:
`{"type": "AUTH", "token": "<access JWT>"}` -> server `{"type": "AUTH_OK"}` javob beradi.
Xabar `WS_AUTH_TIMEOUT_SECONDS` ichida kelmasa yoki token yaroqsiz (muddati o'tgan,
imzosi noto'g'ri, tur access emas) bo'lsa ulanish 4401 bilan yopiladi va room'ga
UMUMAN qo'shilmaydi.

`?token=` query parametri eski (deploy paytida ochiq qolgan) sahifalar uchun vaqtincha
qabul qilinadi. TODO(ROADMAP): bir relizdan keyin olib tashlash.
"""

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.realtime.manager import manager

router = APIRouter()

# WebSocket auth muvaffaqiyatsizligi uchun close kodi. RFC 6455 application
# diapazoni (4000-4999) — 4401 "Unauthorized" HTTP 401 ga ohangdosh.
WS_UNAUTHORIZED_CODE = 4401
# Ulangandan keyin AUTH xabarini kutish muddati — autentifikatsiyasiz ulanish osilib qolmasin.
WS_AUTH_TIMEOUT_SECONDS = 10


async def _receive_auth_token(websocket: WebSocket) -> str | None:
    """Birinchi xabardan tokenni oladi. Kelmasa, JSON emas yoki shakli noto'g'ri — None."""
    try:
        message = await asyncio.wait_for(websocket.receive_json(), WS_AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, ValueError, WebSocketDisconnect):
        return None
    if not isinstance(message, dict) or message.get("type") != "AUTH":
        return None
    token = message.get("token")
    return token if isinstance(token, str) and token else None


@router.websocket("/ws/auctions/{auction_id}")
async def auction_ws(
    websocket: WebSocket,
    auction_id: int,
    token: str | None = Query(default=None),
) -> None:
    """Auksion kanaliga ulanadi va mijoz xabarlarini shu kanalga relay qiladi.

    Room'ga qo'shishdan oldin access JWT tekshiriladi (birinchi AUTH xabari yoki eski
    `?token=`). Handshake'ni AVVAL qabul qilamiz (`accept`), keyin yaroqsiz tokenda
    close kod bilan yopamiz: aks holda close kodi (4401) mijozga yetib
    bormaydi — accept'dan oldingi close oddiy HTTP rad javobiga aylanadi.
    """
    await websocket.accept()

    from_message = token is None
    if from_message:
        token = await _receive_auth_token(websocket)
    payload = decode_access_token(token) if token else None
    if payload is None or payload.get("sub") is None:
        await websocket.close(code=WS_UNAUTHORIZED_CODE)
        return
    if from_message:
        await websocket.send_json({"type": "AUTH_OK"})

    # user_id ni olamiz — kelajakda kim ulanganini kuzatish/bind qilish uchun.
    user_id = int(payload["sub"])  # noqa: F841 — MVP relay'da hali ishlatilmaydi

    manager.add(websocket, auction_id)
    try:
        while True:
            # MVP relay: mijozdan kelgan JSON'ni shu auksionni kuzatayotgan
            # qolgan barcha mijozlarga uzatamiz.
            message = await websocket.receive_json()
            await manager.broadcast(auction_id, message)
    except WebSocketDisconnect:
        manager.disconnect(websocket, auction_id)
