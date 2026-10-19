from enum import StrEnum


class ItemCondition(StrEnum):
    NEW = "new"
    USED = "used"
    REFURBISHED = "refurbished"


class ItemStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PENDING = "pending"
    ACTIVE = "active"
    SOLD = "sold"
    CANCELLED = "cancelled"
    # Taklifli e'lon muddati tugadi, zaxira qolgan (sotuvchi qayta joylay oladi).
    EXPIRED = "expired"


class ListingType(StrEnum):
    """E'lon qanday sotiladi. NULL (item'da) — hali e'lon qilinmagan qoralama.

    OFFER — asosiy rejim: sotuvchi mo'ljal narx (dona uchun) va miqdor beradi,
    xaridorlar istalgan musbat narx va miqdor taklif qiladi, sotuvchi qabul qiladi,
    rad etadi yoki qarshi taklif beradi. Min qadam / anti-sniping YO'Q.
    AUCTION — ixtiyoriy muddatli auksion (bitta dona, eski qoidalar bilan).
    """

    OFFER = "offer"
    AUCTION = "auction"


class OfferStatus(StrEnum):
    """Taklif holati. PENDING — javob kutilmoqda (kimdan — `Offer.awaiting`)."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class OfferParty(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"


class PricingMode(StrEnum):
    """Auksion narx yo'nalishi.

    ASCENDING — klassik: bidlar narxni oshiradi, eng yuqori taklif yutadi.
    DESCENDING — "golland" auksioni: narx vaqt o'tishi bilan qadam-baqadam pasayadi
    (pastki chegara — reserve_price); birinchi "hoziroq sotib olish" yutadi, bid yo'q.
    """

    ASCENDING = "ascending"
    DESCENDING = "descending"


class AuctionStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"
    RESERVE_NOT_MET = "reserve_not_met"


class BidStatus(StrEnum):
    VALID = "valid"
    OUTBID = "outbid"
    CANCELLED = "cancelled"
    # Foydalanuvchi qaytarib oldi (typo/xato stavka). Audit logda qoladi.
    RETRACTED = "retracted"
    # Admin bekor qildi (shill/firibgarlik). Joriy narx qayta hisoblanadi.
    INVALIDATED = "invalidated"


class UserRole(StrEnum):
    USER = "user"
    SELLER = "seller"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"  # to'liq huquq: rol berish, adminlarni boshqarish


# Moderatsiya huquqiga ega rollar. Superadmin — adminning USTKI to'plami:
# admin ruxsat etilgan hamma joyda superadmin ham o'tishi shart. Tekshiruvni
# `role == UserRole.ADMIN` deb yozish superadminni jimgina chetlab o'tadi.
ADMIN_ROLES: frozenset[UserRole] = frozenset({UserRole.ADMIN, UserRole.SUPERADMIN})


def is_admin(role: UserRole) -> bool:
    """Rol admin yoki superadminmi — moderatsiya tekshiruvlari uchun yagona manba."""
    return role in ADMIN_ROLES


class NotificationType(StrEnum):
    OUTBID = "outbid"  # sizni ortda qoldirishdi
    WON = "won"  # auksionda yutdingiz
    SOLD = "sold"  # lotingiz sotildi
    SECOND_CHANCE = "second_chance"  # rezervga yetmadi — sotuvchiga taklif
    ENDING_SOON = "ending_soon"  # auksion tugashiga oz qoldi
    OFFER_RECEIVED = "offer_received"  # sotuvchiga yangi taklif
    OFFER_COUNTERED = "offer_countered"  # qarshi taklif keldi
    OFFER_ACCEPTED = "offer_accepted"  # taklif qabul qilindi -> kelishuv
    OFFER_CLOSED = "offer_closed"  # rad etildi / muddati o'tdi / zaxira tugadi
    PRICE_DROPPED = "price_dropped"  # pasayuvchi auksionda narx sezilarli tushdi
    DUTCH_STARTED = "dutch_started"  # taklifsiz auksion pasayuvchi bosqichga o'tdi
    DEAL_MARKED_SOLD = "deal_marked_sold"  # xaridorga: sotuvchi "Sotildi" belgiladi
    DEAL_COMPLETED = "deal_completed"  # kelishuv yakunlandi (ikkala tomonga)
    DEAL_CANCELLED = "deal_cancelled"  # kelishuv bekor qilindi (sabab bilan)


class DealStatus(StrEnum):
    """Kelishuv holati (docs/DEALS.md). O'tishlar faqat `deal_state` orqali."""

    AGREED = "agreed"  # narx kelishildi, kontaktlar ochiq
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DealCancelReason(StrEnum):
    """Kelishuvni bekor qilish sababi — aybdor tomon shundan aniqlanadi (docs/DEALS.md §7)."""

    NO_RESPONSE = "no_response"  # ikkinchi tomon javob bermadi (48 soatdan keyin)
    CHANGED_MIND = "changed_mind"  # bekor qilgan tomon fikridan qaytdi
    NOT_AS_DESCRIBED = "not_as_described"  # mahsulot e'londagidek emas (aybdor — sotuvchi)
    OTHER = "other"


class ComplaintTargetType(StrEnum):
    ITEM = "item"
    USER = "user"
    AUCTION = "auction"
    MESSAGE = "message"
    DEAL = "deal"


class ComplaintStatus(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ConsentDocumentType(StrEnum):
    """Foydalanuvchi qabul qilishi mumkin bo'lgan huquqiy hujjatlar.

    Nizo chiqqanda "qaysi versiyadagi shartnoma qabul qilingan" savoliga
    javob berish uchun har qabul versiyasi bilan saqlanadi.
    """

    TERMS = "terms"  # foydalanuvchi kelishuvi
    PRIVACY = "privacy"  # maxfiylik siyosati
    AUCTION_RULES = "auction_rules"  # auksion reglamenti
    PUBLIC_OFFER = "public_offer"  # ommaviy oferta (stavka = ofertani qabul)


class OtpPurpose(StrEnum):
    PHONE_VERIFY = "phone_verify"  # telefon raqamni tasdiqlash
    LOGIN = "login"  # OTP orqali kirish
    PASSWORD_RESET = "password_reset"  # parolni tiklash
