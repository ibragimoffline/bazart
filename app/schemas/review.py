from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    """Ikki tomonlama sharh yaratish so'rovi.

    `to_id` klientdan olinmaydi — u orderning ikkinchi tomoni sifatida
    serverda aniqlanadi (muallif buyer bo'lsa -> seller, aksincha).
    """

    deal_id: int
    stars: int = Field(ge=1, le=5)  # 1..5; chegaradan tashqari -> 422
    text: str | None = Field(default=None, max_length=1000)


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deal_id: int
    from_id: int
    to_id: int
    stars: int
    text: str | None
    created_at: datetime
