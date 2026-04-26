"""Seed the product catalog (products + SKUs) when the database is empty."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import ProductORM, SkuORM

logger = logging.getLogger(__name__)

# Full demo catalog: family = dry | wet | treat | dental | topper
CATALOG: list[dict[str, Any]] = [
    {
        "product": {
            "name": "Tails adult complete (dry)",
            "family": "dry",
            "description": "Balanced kibble for adult maintenance.",
        },
        "skus": [
            {"sku": "TAILS-DRY-ADL-CH-2KG", "name": "Adult dry — chicken 2kg", "unit_price_gbp": 24.99, "net_weight_g": 2000},
            {"sku": "TAILS-DRY-ADL-CH-6KG", "name": "Adult dry — chicken 6kg", "unit_price_gbp": 64.99, "net_weight_g": 6000},
            {"sku": "TAILS-DRY-ADL-LS-2KG", "name": "Adult dry — lamb & sweet potato 2kg", "unit_price_gbp": 25.99, "net_weight_g": 2000},
            {"sku": "TAILS-DRY-ADL-SM-2KG", "name": "Adult dry — salmon 2kg", "unit_price_gbp": 26.49, "net_weight_g": 2000},
        ],
    },
    {
        "product": {
            "name": "Tails senior (dry)",
            "family": "dry",
            "description": "Lower calorie, joint-friendly blend.",
        },
        "skus": [
            {"sku": "TAILS-DRY-SR-LM-2KG", "name": "Senior dry — light & mature 2kg", "unit_price_gbp": 27.99, "net_weight_g": 2000},
            {"sku": "TAILS-DRY-SR-LM-6KG", "name": "Senior dry — light & mature 6kg", "unit_price_gbp": 69.99, "net_weight_g": 6000},
        ],
    },
    {
        "product": {
            "name": "Tails puppy (dry)",
            "family": "dry",
            "description": "Growth support for puppies.",
        },
        "skus": [
            {"sku": "TAILS-DRY-PP-CK-1_5KG", "name": "Puppy dry — chicken 1.5kg", "unit_price_gbp": 22.5, "net_weight_g": 1500},
        ],
    },
    {
        "product": {
            "name": "Tails wet complete (trays)",
            "family": "wet",
            "description": "High-moisture complete meals in trays.",
        },
        "skus": [
            {
                "sku": "TAILS-WET-MIX-12x400",
                "name": "Wet — mixed protein 12×400g",
                "unit_price_gbp": 38.99,
                "net_weight_g": 4800,
            },
            {
                "sku": "TAILS-WET-SM-6x400",
                "name": "Wet — salmon 6×400g",
                "unit_price_gbp": 21.99,
                "net_weight_g": 2400,
            },
        ],
    },
    {
        "product": {
            "name": "Tails air-dried treats",
            "family": "treat",
            "description": "Training and reward; account for kcal in daily plan.",
        },
        "skus": [
            {"sku": "TAILS-TRT-FISH-150", "name": "Treats — whitefish bites 150g", "unit_price_gbp": 5.99, "net_weight_g": 150},
            {"sku": "TAILS-TRT-DUCK-150", "name": "Treats — duck strips 150g", "unit_price_gbp": 5.99, "net_weight_g": 150},
        ],
    },
    {
        "product": {
            "name": "Tails dental care",
            "family": "dental",
            "description": "Chews for dental health.",
        },
        "skus": [
            {"sku": "TAILS-DEN-STICK-7", "name": "Dental chews — medium 7 pack", "unit_price_gbp": 8.49, "net_weight_g": 210},
        ],
    },
    {
        "product": {
            "name": "Tails toppers & broths",
            "family": "topper",
            "description": "Optional palatability boost; not complete diet alone.",
        },
        "skus": [
            {"sku": "TAILS-TOP-GRV-3x", "name": "Topper — gravy 3×80g", "unit_price_gbp": 3.99, "net_weight_g": 240},
        ],
    },
    {
        "product": {
            "name": "Tails delivery & packaging",
            "family": "service",
            "description": "Recurring box and cold-pack handling.",
        },
        "skus": [
            {"sku": "TAILS-SVC-BOX-GB", "name": "Subscription box & delivery (UK)", "unit_price_gbp": 4.5, "net_weight_g": None},
        ],
    },
]


def seed_catalog_if_empty(db: Session) -> None:
    if db.query(SkuORM).count() > 0:
        return
    for block in CATALOG:
        p = block["product"]
        product = ProductORM(name=p["name"], family=p["family"], description=p.get("description"))
        db.add(product)
        db.flush()
        for s in block["skus"]:
            db.add(
                SkuORM(
                    product_id=product.id,
                    sku=s["sku"],
                    name=s["name"],
                    unit_price_gbp=s["unit_price_gbp"],
                    net_weight_g=s.get("net_weight_g"),
                    is_active=True,
                )
            )
    db.commit()
    logger.info("Seeded product catalog: %d products, %d SKUs", len(CATALOG), len([s for b in CATALOG for s in b["skus"]]))
