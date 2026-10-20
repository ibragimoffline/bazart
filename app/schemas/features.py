from pydantic import BaseModel


class FeatureFlags(BaseModel):
    """Frontend uchun yoqilgan imkoniyatlar — UI va API bitta manbadan (settings) o'qiydi."""

    ascending_auction: bool
