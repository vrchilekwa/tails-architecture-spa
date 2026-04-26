from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "tails-target-state-api"


class DogProfileCreate(BaseModel):
    name: str
    breed: str
    age_years: float = Field(ge=0)
    weight_kg: float = Field(gt=0)
    activity_level: Literal["low", "moderate", "high"]
    health_goals: list[str] = Field(default_factory=list)
    sensitivities: list[str] = Field(default_factory=list)


class DogProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    owner_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data: DogProfileCreate


class PlanQuoteRequest(BaseModel):
    dog_id: UUID
    include_wet_food: bool = False
    include_treats: bool = False
    include_dental_chews: bool = False


class PlanQuoteResponse(BaseModel):
    dog_id: UUID
    kcal_per_day: int
    monthly_price_gbp: float
    recommended_recipe: str
    reasons: list[str]


class CatalogSku(BaseModel):
    id: UUID
    sku: str
    name: str
    family: str
    product_name: str
    product_id: UUID
    unit_price_gbp: float
    net_weight_g: int | None = None
    is_active: bool = True


class PersonalizedCatalogSku(CatalogSku):
    list_price_gbp: float
    customer_price_gbp: float
    discount_pct: float
    pricing_tier: str


class ProductSummary(BaseModel):
    id: UUID
    name: str
    family: str
    description: str | None
    skus: list[CatalogSku]


class OrderLineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sku_code: str
    product_name: str
    quantity: int
    unit_price_gbp: float
    line_total_gbp: float


class SubscriptionCreate(BaseModel):
    customer_id: str
    dog_id: UUID
    cadence_days: int = Field(default=30, ge=7, le=60)


class Subscription(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    customer_id: str
    dog_id: UUID
    cadence_days: int
    status: Literal["active", "paused", "cancelled", "skipped"] = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CheckoutLineItem(BaseModel):
    sku: str = Field(min_length=1, max_length=64, description="Catalog sku code, e.g. TAILS-DRY-ADL-CH-2KG")
    quantity: int = Field(ge=1, le=99)


class CheckoutRequest(BaseModel):
    customer_id: str
    subscription_id: UUID
    lines: list[CheckoutLineItem] = Field(
        min_length=1, description="Cart: SKU codes from GET /catalog with per-line quantity"
    )
    promo_code: str | None = None


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    customer_id: str
    subscription_id: UUID
    subtotal_gbp: float = 0.0
    discount_gbp: float = 0.0
    total_gbp: float
    status: Literal["placed", "paid", "packed", "shipped", "delivered"] = "placed"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    lines: list[OrderLineItem] = Field(default_factory=list)


class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AwsCognitoExchangeRequest(BaseModel):
    id_token: str = Field(min_length=20)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthMeResponse(BaseModel):
    subject: str
    email: str | None = None
    provider: str | None = None


class GoogleOIDCStartResponse(BaseModel):
    authorization_url: str
    note: str
