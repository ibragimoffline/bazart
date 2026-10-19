"""Kelishuv (deal) holati state machine (docs/DEALS.md §3).

Qo'lda `status = ...` taqiqlangan: har o'tish shu jadval orqali tekshiriladi. `completed` va
`cancelled` — yakuniy. E5.2 da `fee_pending` qo'shiladi (fee_pending -> agreed | cancelled),
shuning uchun o'tishlar jadval sifatida saqlanadi, if-zanjir emas.
"""

from app.models.enums import DealStatus

ALLOWED_TRANSITIONS: dict[DealStatus, frozenset[DealStatus]] = {
    DealStatus.AGREED: frozenset({DealStatus.COMPLETED, DealStatus.CANCELLED}),
    DealStatus.COMPLETED: frozenset(),
    DealStatus.CANCELLED: frozenset(),
}


class InvalidDealTransition(Exception):
    def __init__(self, current: DealStatus, target: DealStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Kelishuv holati {current.value} -> {target.value} taqiqlangan")


def assert_deal_transition(current: DealStatus, target: DealStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidDealTransition(current, target)
