import secrets
from collections import defaultdict
from hashlib import sha256
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.auth import build_google_authorization_url, create_access_token, decode_access_token, hash_password, verify_password
from app.aws_cognito import verify_cognito_id_token
from app.catalog_seed import seed_catalog_if_empty
from app.config import settings
from app.database import Base, engine, get_db, SessionLocal
from app.db_models import DogProfileORM, OrderLineORM, OrderORM, SkuORM, ProductORM, SubscriptionORM, UserORM
from app.events import EventConsumer, EventPublisher
from app.models import (
    CatalogSku,
    CheckoutRequest,
    DogProfile,
    DogProfileCreate,
    AwsCognitoExchangeRequest,
    AuthMeResponse,
    GoogleOIDCStartResponse,
    HealthResponse,
    Order,
    PlanQuoteRequest,
    PlanQuoteResponse,
    PersonalizedCatalogSku,
    ProductSummary,
    Subscription,
    SubscriptionCreate,
    TokenResponse,
    UserLoginRequest,
    UserSignupRequest,
)
from app.order_mapping import order_orm_to_api

app = FastAPI(title=settings.app_name, version=settings.app_version, description="Target-state backend with PostgreSQL, Kafka, JWT, and OIDC stubs.")
events = EventPublisher()
consumer = EventConsumer()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_catalog_if_empty(db)
    finally:
        db.close()
    await events.start()
    await consumer.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await consumer.stop()
    await events.stop()


_bearer = HTTPBearer(auto_error=False)
DEFAULT_PERMISSIONS = ["catalog:read:personalized", "orders:read:self"]


def get_current_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None or (credentials.scheme or "").lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return str(claims.get("sub"))


def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if credentials is None or (credentials.scheme or "").lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def require_permission(permission: str):
    def _check_permission(claims: dict = Depends(get_current_claims)) -> None:
        permissions = claims.get("permissions")
        if not isinstance(permissions, list) or permission not in permissions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")

    return _check_permission


def _sku_to_catalog(s: SkuORM) -> CatalogSku:
    p = s.product
    return CatalogSku(
        id=s.id,
        sku=s.sku,
        name=s.name,
        family=p.family,
        product_name=p.name,
        product_id=p.id,
        unit_price_gbp=s.unit_price_gbp,
        net_weight_g=s.net_weight_g,
        is_active=s.is_active,
    )


def _subject_discount_pct(subject: str, sku_code: str) -> float:
    digest = sha256(f"{subject}:{sku_code}".encode("utf-8")).digest()
    # Deterministic per-user per-sku discount between 0% and 12%.
    return round((digest[0] % 13), 2)


def _sku_to_personalized_catalog(s: SkuORM, subject: str) -> PersonalizedCatalogSku:
    base = _sku_to_catalog(s)
    discount_pct = _subject_discount_pct(subject, s.sku)
    customer_price = round(base.unit_price_gbp * (1 - (discount_pct / 100.0)), 2)
    tier = "contract" if discount_pct >= 8 else "standard"
    return PersonalizedCatalogSku(
        **base.model_dump(),
        list_price_gbp=base.unit_price_gbp,
        customer_price_gbp=customer_price,
        discount_pct=discount_pct,
        pricing_tier=tier,
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/catalog", response_model=list[CatalogSku], tags=["Catalog"])
def list_catalog(db: Session = Depends(get_db)) -> list[CatalogSku]:
    """Flat list of active sellable SKUs (product identifiers for cart line items)."""
    rows = (
        db.query(SkuORM)
        .options(joinedload(SkuORM.product))
        .filter(SkuORM.is_active.is_(True))
        .order_by(SkuORM.sku)
        .all()
    )
    return [_sku_to_catalog(s) for s in rows]


@app.get("/catalog/me", response_model=list[PersonalizedCatalogSku], tags=["Catalog"])
def list_catalog_for_current_user(
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
    _: None = Depends(require_permission("catalog:read:personalized")),
) -> list[PersonalizedCatalogSku]:
    """Authenticated catalog view with mock deterministic user-specific pricing."""
    rows = (
        db.query(SkuORM)
        .options(joinedload(SkuORM.product))
        .filter(SkuORM.is_active.is_(True))
        .order_by(SkuORM.sku)
        .all()
    )
    return [_sku_to_personalized_catalog(s, subject=subject) for s in rows]


@app.get("/catalog/products", response_model=list[ProductSummary], tags=["Catalog"])
def list_catalog_by_product(db: Session = Depends(get_db)) -> list[ProductSummary]:
    """Product catalog with nested SKUs per product line."""
    products = db.query(ProductORM).options(joinedload(ProductORM.skus)).order_by(ProductORM.name).all()
    out: list[ProductSummary] = []
    for p in products:
        active = [s for s in p.skus if s.is_active]
        if not active:
            continue
        out.append(
            ProductSummary(
                id=p.id,
                name=p.name,
                family=p.family,
                description=p.description,
                skus=[_sku_to_catalog(s) for s in active],
            )
        )
    return out


@app.post("/auth/signup", response_model=TokenResponse, tags=["Auth"])
def signup(payload: UserSignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(UserORM).filter(UserORM.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")
    user = UserORM(email=payload.email, hashed_password=hash_password(payload.password), provider="local")
    db.add(user)
    db.commit()
    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "email": user.email,
            "provider": "local",
            "permissions": DEFAULT_PERMISSIONS,
        },
    )
    return TokenResponse(access_token=token)


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(UserORM).filter(UserORM.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "email": user.email,
            "provider": user.provider,
            "permissions": DEFAULT_PERMISSIONS,
        },
    )
    return TokenResponse(access_token=token)


@app.post("/auth/aws/exchange", response_model=TokenResponse, tags=["Auth"])
def exchange_aws_cognito_token(payload: AwsCognitoExchangeRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        claims = verify_cognito_id_token(payload.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    cognito_sub = str(claims.get("sub") or "")
    if not cognito_sub:
        raise HTTPException(status_code=401, detail="AWS token missing sub claim")
    email = claims.get("email") or f"cognito_{cognito_sub[:8]}@stub.tails.com"

    user = db.query(UserORM).filter(UserORM.email == email).first()
    if not user:
        user = UserORM(email=email, hashed_password=hash_password(secrets.token_urlsafe(24)), provider="aws-cognito")
        db.add(user)
        db.commit()

    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "email": user.email,
            "provider": "aws-cognito",
            "aws_sub": cognito_sub,
            "permissions": DEFAULT_PERMISSIONS,
        },
    )
    return TokenResponse(access_token=token)


@app.get("/auth/me", response_model=AuthMeResponse, tags=["Auth"])
def auth_me(claims: dict = Depends(get_current_claims)) -> AuthMeResponse:
    return AuthMeResponse(
        subject=str(claims.get("sub") or ""),
        email=claims.get("email"),
        provider=claims.get("provider"),
    )


@app.get("/auth/google/start", response_model=GoogleOIDCStartResponse, tags=["Auth"])
def google_start() -> GoogleOIDCStartResponse:
    state = secrets.token_urlsafe(16)
    return GoogleOIDCStartResponse(
        authorization_url=build_google_authorization_url(state=state),
        note="OIDC stub endpoint: callback currently trusts input code and creates/loads a local Google user.",
    )


@app.get("/auth/google/callback", response_model=TokenResponse, tags=["Auth"])
def google_callback(code: str, db: Session = Depends(get_db)) -> TokenResponse:
    stub_email = f"google_user_{code[:8]}@stub.tails.com"
    user = db.query(UserORM).filter(UserORM.email == stub_email).first()
    if not user:
        user = UserORM(email=stub_email, hashed_password=hash_password(secrets.token_urlsafe(24)), provider="google")
        db.add(user)
        db.commit()
    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "email": user.email,
            "provider": "google",
            "permissions": DEFAULT_PERMISSIONS,
        },
    )
    return TokenResponse(access_token=token)


@app.post("/dogs", response_model=DogProfile, tags=["Dog Profile"])
async def create_dog_profile(payload: DogProfileCreate, db: Session = Depends(get_db), subject: str = Depends(get_current_subject)) -> DogProfile:
    dog = DogProfileORM(
        owner_id=subject,
        name=payload.name,
        breed=payload.breed,
        age_years=payload.age_years,
        weight_kg=payload.weight_kg,
        activity_level=payload.activity_level,
        health_goals=payload.health_goals,
        sensitivities=payload.sensitivities,
    )
    db.add(dog)
    db.commit()
    db.refresh(dog)
    await events.publish("dogs", "DogProfileCaptured", {"dog_id": str(dog.id), "owner_id": subject})

    return DogProfile(
        id=dog.id,
        owner_id=dog.owner_id,
        created_at=dog.created_at,
        data=DogProfileCreate(
            name=dog.name,
            breed=dog.breed,
            age_years=dog.age_years,
            weight_kg=dog.weight_kg,
            activity_level=dog.activity_level,
            health_goals=dog.health_goals,
            sensitivities=dog.sensitivities,
        ),
    )


@app.get("/dogs/{dog_id}", response_model=DogProfile, tags=["Dog Profile"])
def get_dog_profile(dog_id: UUID, db: Session = Depends(get_db), subject: str = Depends(get_current_subject)) -> DogProfile:
    dog = db.query(DogProfileORM).filter(DogProfileORM.id == dog_id, DogProfileORM.owner_id == subject).first()
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    return DogProfile(
        id=dog.id,
        owner_id=dog.owner_id,
        created_at=dog.created_at,
        data=DogProfileCreate(
            name=dog.name,
            breed=dog.breed,
            age_years=dog.age_years,
            weight_kg=dog.weight_kg,
            activity_level=dog.activity_level,
            health_goals=dog.health_goals,
            sensitivities=dog.sensitivities,
        ),
    )


@app.post("/plans/quote", response_model=PlanQuoteResponse, tags=["Nutrition Planning"])
async def quote_plan(payload: PlanQuoteRequest, db: Session = Depends(get_db), subject: str = Depends(get_current_subject)) -> PlanQuoteResponse:
    dog = db.query(DogProfileORM).filter(DogProfileORM.id == payload.dog_id, DogProfileORM.owner_id == subject).first()
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")

    base_price = max(19.99, round(dog.weight_kg * 1.3, 2))
    add_on_price = 0.0
    reasons = [f"Base from weight: {dog.weight_kg}kg", f"Activity: {dog.activity_level}"]
    if payload.include_wet_food:
        add_on_price += 6.0
        reasons.append("Added wet food bundle")
    if payload.include_treats:
        add_on_price += 4.0
        reasons.append("Added treats bundle")
    if payload.include_dental_chews:
        add_on_price += 5.0
        reasons.append("Added dental chews bundle")

    quote = PlanQuoteResponse(
        dog_id=payload.dog_id,
        kcal_per_day=int(95 * (dog.weight_kg ** 0.75)),
        monthly_price_gbp=round(base_price + add_on_price, 2),
        recommended_recipe=f"Tailored blend for {dog.breed} with goals: {', '.join(dog.health_goals) or 'general wellness'}",
        reasons=reasons,
    )
    await events.publish("plans", "PlanQuoted", {"dog_id": str(payload.dog_id), "price": quote.monthly_price_gbp})
    return quote


@app.post("/subscriptions", response_model=Subscription, tags=["Subscription"])
async def create_subscription(payload: SubscriptionCreate, db: Session = Depends(get_db), subject: str = Depends(get_current_subject)) -> Subscription:
    dog = db.query(DogProfileORM).filter(DogProfileORM.id == payload.dog_id, DogProfileORM.owner_id == subject).first()
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")

    subscription = SubscriptionORM(customer_id=payload.customer_id, dog_id=payload.dog_id, cadence_days=payload.cadence_days, status="active")
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    await events.publish("subscriptions", "SubscriptionActivated", {"subscription_id": str(subscription.id)})
    return Subscription.model_validate(subscription)


@app.post("/subscriptions/{subscription_id}/pause", response_model=Subscription, tags=["Subscription"])
async def pause_subscription(subscription_id: UUID, db: Session = Depends(get_db), subject: str = Depends(get_current_subject)) -> Subscription:
    subscription = db.query(SubscriptionORM).filter(SubscriptionORM.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    subscription.status = "paused"
    db.commit()
    db.refresh(subscription)
    await events.publish("subscriptions", "SubscriptionPausedOrSkipped", {"subscription_id": str(subscription.id), "status": "paused", "actor": subject})
    return Subscription.model_validate(subscription)


@app.post("/checkout", response_model=Order, tags=["Cart & Checkout"])
async def checkout(payload: CheckoutRequest, db: Session = Depends(get_db), subject: str = Depends(get_current_subject)) -> Order:
    if payload.customer_id != subject:
        raise HTTPException(status_code=403, detail="customer_id must match authenticated user")
    subscription = db.query(SubscriptionORM).filter(SubscriptionORM.id == payload.subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if subscription.customer_id != payload.customer_id:
        raise HTTPException(status_code=403, detail="Subscription does not belong to this customer")

    merged: dict[str, int] = defaultdict(int)
    for li in payload.lines:
        code = li.sku.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Empty sku in line item")
        merged[code] += li.quantity

    skus_by_code: dict[str, SkuORM] = {}
    for code in merged:
        s = (
            db.query(SkuORM)
            .options(joinedload(SkuORM.product))
            .filter(SkuORM.sku == code, SkuORM.is_active.is_(True))
            .first()
        )
        if not s:
            raise HTTPException(status_code=400, detail=f"Unknown or inactive SKU: {code}")
        skus_by_code[code] = s

    subtotal = 0.0
    order = OrderORM(
        customer_id=payload.customer_id,
        subscription_id=payload.subscription_id,
        subtotal_gbp=0.0,
        discount_gbp=0.0,
        total_gbp=0.0,
        status="paid",
    )
    for code, qty in merged.items():
        s = skus_by_code[code]
        p = s.product
        unit = s.unit_price_gbp
        line_t = round(qty * unit, 2)
        subtotal += line_t
        product_name = f"{p.name} — {s.name}"
        order.lines.append(
            OrderLineORM(
                sku_id=s.id,
                sku_code=s.sku,
                product_name=product_name,
                quantity=qty,
                unit_price_gbp=unit,
                line_total_gbp=line_t,
            )
        )

    subtotal = round(subtotal, 2)
    promo = bool((payload.promo_code or "").strip())
    discount = round(subtotal * 0.2, 2) if promo else 0.0
    total = round(subtotal - discount, 2)
    order.subtotal_gbp = subtotal
    order.discount_gbp = discount
    order.total_gbp = total

    db.add(order)
    db.commit()
    db.refresh(order)
    # refresh loads lines; ensure relationship present
    await events.publish(
        "orders",
        "CheckoutCompleted",
        {
            "order_id": str(order.id),
            "subscription_id": str(payload.subscription_id),
            "actor": subject,
            "subtotal_gbp": subtotal,
            "total_gbp": total,
            "line_skus": [{"sku": ln.sku_code, "quantity": ln.quantity} for ln in order.lines],
        },
    )
    await events.publish("orders", "OrderPlaced", {"order_id": str(order.id)})
    return order_orm_to_api(order)


@app.get("/orders", response_model=list[Order], tags=["Orders"])
def list_orders(
    customer_id: str,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
    _: None = Depends(require_permission("orders:read:self")),
) -> list[Order]:
    if customer_id != subject:
        raise HTTPException(status_code=403, detail="customer_id must match authenticated user")
    rows = (
        db.query(OrderORM)
        .options(joinedload(OrderORM.lines))
        .filter(OrderORM.customer_id == customer_id)
        .order_by(OrderORM.created_at.desc())
        .all()
    )
    return [order_orm_to_api(o) for o in rows]


@app.get("/orders/{order_id}", response_model=Order, tags=["Orders"])
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    subject: str = Depends(get_current_subject),
    _: None = Depends(require_permission("orders:read:self")),
) -> Order:
    order = (
        db.query(OrderORM)
        .options(joinedload(OrderORM.lines))
        .filter(OrderORM.id == order_id, OrderORM.customer_id == subject)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_orm_to_api(order)
