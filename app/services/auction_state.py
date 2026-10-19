"""Auksion holati state machine.

Auksion holati FAQAT shu yerdagi ruxsat etilgan o'tishlar orqali o'zgaradi.
Qo'lda `auction.status = ...` yozish TAQIQ — bu invariantlarni chetlab
o'tadi (masalan g'olibsiz ENDED, yoki bidli auksionni bekor qilish).

Ikki daraja:
  ALLOWED_TRANSITIONS   — umuman qonuniy o'tishlar (tizim + sotuvchi).
  SELLER_ALLOWED_TARGETS — sotuvchi API orqali QO'LDA so'ray oladigan
                           yakuniy holatlar. Qolganlari faqat tizim
                           (close worker, aktivlashtirish) tomonidan.
"""

from app.models.enums import AuctionStatus

# Qaysi holatdan qaysi holatlarga o'tish mumkin.
ALLOWED_TRANSITIONS: dict[AuctionStatus, frozenset[AuctionStatus]] = {
    AuctionStatus.SCHEDULED: frozenset({AuctionStatus.ACTIVE, AuctionStatus.CANCELLED}),
    AuctionStatus.ACTIVE: frozenset(
        {AuctionStatus.ENDED, AuctionStatus.RESERVE_NOT_MET, AuctionStatus.CANCELLED}
    ),
    # RESERVE_NOT_MET -> ENDED: second-chance offer. Sotuvchi rezervga yetmagan
    # eng yuqori bidderga sotishga rozi bo'lsa, auksion ENDED bo'lib deal
    # yaratiladi. Bu YAGONA chiqish yo'li — boshqa holatga o'tib bo'lmaydi.
    AuctionStatus.RESERVE_NOT_MET: frozenset({AuctionStatus.ENDED}),
    # Yakuniy holatlar — bu yerdan hech qayerga o'tilmaydi.
    AuctionStatus.ENDED: frozenset(),
    AuctionStatus.CANCELLED: frozenset(),
}

# Sotuvchi PATCH orqali qo'lda faqat bekor qila oladi. ENDED/RESERVE_NOT_MET
# faqat close oqimi (g'olib aniqlangach), ACTIVE faqat aktivlashtirish
# orqali qo'yiladi — aks holda sotuvchi deal/g'olib mantiqini chetlab o'tadi.
SELLER_ALLOWED_TARGETS: frozenset[AuctionStatus] = frozenset({AuctionStatus.CANCELLED})


class InvalidAuctionTransition(Exception):
    """Taqiqlangan holat o'tishi."""

    def __init__(self, current: AuctionStatus, target: AuctionStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Auksion holati {current.value} -> {target.value} taqiqlangan")


def assert_transition(current: AuctionStatus, target: AuctionStatus) -> None:
    """`current` dan `target` ga o'tish qonuniy bo'lmasa xato ko'taradi."""
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidAuctionTransition(current, target)
