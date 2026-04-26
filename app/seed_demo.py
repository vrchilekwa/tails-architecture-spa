"""
Demo data "agent" — contrived but coherent scenarios for local/staging:
users, dog profiles, subscriptions, and past orders with order lines that reference
**real** catalog SKUs so subtotals and line totals match checkout math.

Run after the API database exists and catalog is seeded (startup or catalog_seed):
  python -m app.seed_demo
  python -m app.seed_demo --force   # remove prior demo users + related rows, re-seed

In Docker (from project root):
  docker compose exec api python -m app.seed_demo

All demo logins use the same password (see DEMO_PASSWORD after seed runs).
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.auth import hash_password
from app.catalog_seed import seed_catalog_if_empty
from app.db_models import (
    DogProfileORM,
    OrderLineORM,
    OrderORM,
    SkuORM,
    SubscriptionORM,
    UserORM,
)
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Fixed credentials so Postman/scripts can sign in; document in logs.
DEMO_PASSWORD = "DemoPass11"
DEMO_EMAILS: tuple[str, ...] = (
    "helen.murray@demo.tails",
    "james.cho@demo.tails",
    "sarah.kim@demo.tails",
    "luca.patel@demo.tails",
)


@dataclass
class _OrderSpec:
    """Line items: sku code + quantity; subtotals = sum(qty * catalog unit) before promo."""

    lines: list[tuple[str, int]]  # (sku_code, quantity)
    use_promo: bool = False
    status: str = "paid"
    days_ago: int = 7


@dataclass
class _UserScenario:
    email: str
    # dogs: (name, breed, age, weight, activity, goals, sensitivities)
    dogs: list[tuple[str, str, float, float, str, list[str], list[str]]]
    # subscription: (dog_index, cadence_days, status) or None; dog_index 0-based
    subscription: tuple[int, int, str] | None
    # orders: each after dogs/subs are created; subscription_index 0 = first sub
    orders: list[_OrderSpec] = field(default_factory=list)


def _lookup_sku(db: Session, code: str) -> SkuORM:
    s = db.query(SkuORM).options(joinedload(SkuORM.product)).filter(SkuORM.sku == code, SkuORM.is_active.is_(True)).first()
    if not s:
        raise RuntimeError(f"Catalog missing SKU {code!r}. Ensure the catalog is seeded (API startup or first-time seed).")
    return s


def _line_product_name(s: SkuORM) -> str:
    p = s.product
    return f"{p.name} — {s.name}"


def _add_order(
    db: Session,
    *,
    customer_id: str,
    subscription_id: UUID,
    spec: _OrderSpec,
) -> None:
    merged: dict[str, int] = {}
    for code, qty in spec.lines:
        c = code.strip()
        if c not in merged:
            merged[c] = 0
        merged[c] += qty
    if not merged:
        raise ValueError("order with no line items")
    subtotal = 0.0
    order = OrderORM(
        customer_id=customer_id,
        subscription_id=subscription_id,
        subtotal_gbp=0.0,
        discount_gbp=0.0,
        total_gbp=0.0,
        status=spec.status,
    )
    order.created_at = datetime.now(timezone.utc) - timedelta(days=spec.days_ago)
    for code, qty in merged.items():
        s = _lookup_sku(db, code)
        p = s.product
        unit = s.unit_price_gbp
        line_t = round(qty * unit, 2)
        subtotal += line_t
        order.lines.append(
            OrderLineORM(
                sku_id=s.id,
                sku_code=s.sku,
                product_name=f"{p.name} — {s.name}",
                quantity=qty,
                unit_price_gbp=unit,
                line_total_gbp=line_t,
            )
        )
    subtotal = round(subtotal, 2)
    discount = round(subtotal * 0.2, 2) if spec.use_promo else 0.0
    total = round(subtotal - discount, 2)
    order.subtotal_gbp = subtotal
    order.discount_gbp = discount
    order.total_gbp = total
    db.add(order)


def _remove_demo_rows(db: Session, emails: Sequence[str]) -> int:
    """Delete demo users and dependent rows. Returns number of users deleted."""
    users = db.query(UserORM).filter(UserORM.email.in_(list(emails))).all()
    if not users:
        return 0
    ids = [u.id for u in users]
    cids = [str(uid) for uid in ids]
    for cid in cids:
        for order in db.query(OrderORM).filter(OrderORM.customer_id == cid).all():
            db.delete(order)
    for sid in cids:
        for sub in db.query(SubscriptionORM).filter(SubscriptionORM.customer_id == sid).all():
            db.delete(sub)
    for cid in cids:
        for dog in db.query(DogProfileORM).filter(DogProfileORM.owner_id == cid).all():
            db.delete(dog)
    n = 0
    for u in users:
        db.delete(u)
        n += 1
    db.commit()
    return n


# Real-world-flavoured scenarios: weights align for quote-style kcal (large dog vs small vs senior).
SCENARIOS: list[_UserScenario] = [
    _UserScenario(
        email="helen.murray@demo.tails",
        dogs=[
            (
                "Cooper",
                "Labrador Retriever",
                4.0,
                32.0,
                "high",
                ["lean muscle", "hip care"],
                [],
            )
        ],
        subscription=(0, 30, "active"),
        orders=[
            # Monthly box: bulk dry + wet + delivery (all valid SKUs)
            _OrderSpec(
                [
                    ("TAILS-DRY-ADL-CH-6KG", 1),
                    ("TAILS-WET-MIX-12x400", 1),
                    ("TAILS-SVC-BOX-GB", 1),
                ],
                use_promo=False,
                status="delivered",
                days_ago=40,
            ),
            # Top-up: smaller dry + treats + dental; promo
            _OrderSpec(
                [
                    ("TAILS-DRY-ADL-CH-2KG", 1),
                    ("TAILS-TRT-FISH-150", 2),
                    ("TAILS-DEN-STICK-7", 1),
                ],
                use_promo=True,
                status="shipped",
                days_ago=5,
            ),
        ],
    ),
    _UserScenario(
        email="james.cho@demo.tails",
        dogs=[
            (
                "Mabel",
                "Border Collie",
                9.0,
                18.5,
                "moderate",
                ["cognitive", "weight"],
                ["grain"],
            )
        ],
        subscription=(0, 30, "paused"),
        orders=[
            _OrderSpec(
                [("TAILS-DRY-SR-LM-2KG", 1), ("TAILS-SVC-BOX-GB", 1), ("TAILS-DEN-STICK-7", 1)],
                use_promo=False,
                status="delivered",
                days_ago=60,
            ),
        ],
    ),
    _UserScenario(
        email="sarah.kim@demo.tails",
        dogs=[
            (
                "Pip",
                "English Cocker Spaniel",
                0.5,
                8.2,
                "moderate",
                ["puppy growth"],
                ["beef"],
            )
        ],
        subscription=None,
        orders=[],
    ),
    _UserScenario(
        email="luca.patel@demo.tails",
        dogs=[
            ("Biscuit", "French Bulldog", 3.0, 12.0, "low", ["sensitive skin"], ["chicken"]),
            ("Koji", "Shiba Inu", 2.0, 9.0, "moderate", ["weight"], []),
        ],
        # Second dog's subscription: multi-dog household
        subscription=(1, 30, "active"),
        orders=[
            _OrderSpec(
                [("TAILS-DRY-ADL-LS-2KG", 1), ("TAILS-TRT-DUCK-150", 1), ("TAILS-SVC-BOX-GB", 1)],
                use_promo=True,
                status="paid",
                days_ago=1,
            ),
        ],
    ),
]


def _already_seeded(db: Session) -> bool:
    n = db.query(UserORM).filter(UserORM.email.in_(list(DEMO_EMAILS))).count()
    return n > 0


def seed_demo_data(db: Session, *, force: bool = False) -> None:
    if force:
        n = _remove_demo_rows(db, DEMO_EMAILS)
        if n:
            logger.info("Removed %d demo user(s) and their orders/subscriptions/dogs", n)
    elif _already_seeded(db):
        print(
            f"Demo data already present (one of: {', '.join(DEMO_EMAILS)}). "
            f"Use --force to remove and re-seed.",
            file=sys.stderr,
        )
        return

    seed_catalog_if_empty(db)
    for scenario in SCENARIOS:
        if db.query(UserORM).filter(UserORM.email == scenario.email).first():
            continue
        user = UserORM(
            email=scenario.email,
            hashed_password=hash_password(DEMO_PASSWORD),
            provider="local",
        )
        db.add(user)
        db.flush()
        cid = str(user.id)
        dog_rows: list[DogProfileORM] = []
        for name, breed, age, weight, act, goals, sens in scenario.dogs:
            d = DogProfileORM(
                owner_id=cid,
                name=name,
                breed=breed,
                age_years=age,
                weight_kg=weight,
                activity_level=act,
                health_goals=goals,
                sensitivities=sens,
            )
            db.add(d)
            dog_rows.append(d)
        db.flush()
        sub_id: UUID | None = None
        if scenario.subscription is not None:
            d_idx, cad, st = scenario.subscription
            dog = dog_rows[d_idx]
            sub = SubscriptionORM(customer_id=cid, dog_id=dog.id, cadence_days=cad, status=st)
            db.add(sub)
            db.flush()
            sub_id = sub.id
        for spec in scenario.orders:
            if sub_id is None:
                raise RuntimeError(f"Scenario {scenario.email} has orders but no subscription")
            _add_order(db, customer_id=cid, subscription_id=sub_id, spec=spec)
    db.commit()
    print("Demo data seeded. Log in with any of:")
    for e in DEMO_EMAILS:
        print(f"  {e} / {DEMO_PASSWORD}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="Delete demo@ rows and re-seed")
    args = p.parse_args()
    db = SessionLocal()
    try:
        seed_demo_data(db, force=args.force)
    except Exception:
        db.rollback()
        logger.exception("Seeding failed")
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
