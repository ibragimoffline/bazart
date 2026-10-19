"""Celery fon vazifalari.

Modullar:
  * scheduled     — davriy (beat): auksion yopish, takliflar muddati, eslatmalar.
  * notifications — push yetkazish (queue).
  * email         — email yuborish (queue).
  * dispatch      — enqueue() yordamchisi (broker yo'q bo'lsa inline zaxira).
"""

# Worker faqat vazifa modullarini yuklaydi — barcha modellar ro'yxatdan o'tmasa
# SQLAlchemy mapper'lari sozlanmaydi (masalan Auction -> Item, Deal -> Offer munosabatlari) va beat
# vazifalarining birinchi ORM so'rovida yiqiladi. Web ilova, testlar va scripts/ buni
# app.db.base orqali qiladi; worker uchun ham shu yerda.
import app.db.base  # noqa: E402, F401
