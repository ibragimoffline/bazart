"""Order holati state machine.

Qo'lda status yozish faqat ruxsat etilgan o'tishlar orqali (grifing va izchillik
buzilishining oldi). Faza E o'tish davri: to'lov oqimi yo'q, sotuvchi order'ni
o'zi yakunlaydi yoki bekor qiladi; E2 da `deal_state` bilan almashadi.
"""

from app.models.enums import OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING_PAYMENT: frozenset(
        {OrderStatus.PICKUP_PENDING, OrderStatus.COMPLETED, OrderStatus.CANCELLED}
    ),
    OrderStatus.PICKUP_PENDING: frozenset({OrderStatus.COMPLETED, OrderStatus.CANCELLED}),
    OrderStatus.COMPLETED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


class InvalidOrderTransition(Exception):
    def __init__(self, current: OrderStatus, target: OrderStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Order holati {current.value} -> {target.value} taqiqlangan")


def assert_order_transition(current: OrderStatus, target: OrderStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidOrderTransition(current, target)
