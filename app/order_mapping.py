"""Map OrderORM to API Order (including line items)."""

from app.db_models import OrderORM
from app.models import Order, OrderLineItem


def order_orm_to_api(order: OrderORM) -> Order:
    subtotal = order.subtotal_gbp
    discount = order.discount_gbp
    lines = order.lines or []
    if not lines and subtotal == 0.0 and order.total_gbp and order.total_gbp > 0:
        # legacy rows created before subtotal was stored
        subtotal = order.total_gbp
        discount = 0.0
    return Order(
        id=order.id,
        customer_id=order.customer_id,
        subscription_id=order.subscription_id,
        subtotal_gbp=subtotal,
        discount_gbp=discount,
        total_gbp=order.total_gbp,
        status=order.status,  # type: ignore[arg-type]
        created_at=order.created_at,
        lines=[
            OrderLineItem(
                id=ln.id,
                sku_code=ln.sku_code,
                product_name=ln.product_name,
                quantity=ln.quantity,
                unit_price_gbp=ln.unit_price_gbp,
                line_total_gbp=ln.line_total_gbp,
            )
            for ln in lines
        ],
    )
