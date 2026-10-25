"""Políticas de promociones y puntos del dominio de ventas.

Estas funciones no conocen HTTP ni SQLite: reciben datos de la venta y reglas
activas, y devuelven la decisión comercial que usa el caso de uso.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def applies_to(promotion: Mapping[str, Any], product_id: int, category: str) -> bool:
    """Una regla aplica al producto indicado o a toda su familia."""
    return promotion["product_id"] == product_id or (
        bool(promotion["category"]) and promotion["category"] == category
    )


def qualifies(quantity: float, minimum: float) -> bool:
    """Indica si la cantidad de la línea alcanza el mínimo de la promoción."""
    return float(quantity) >= float(minimum)


def points_for(quantity: float, promotion: Mapping[str, Any]) -> int:
    """Calcula los puntos ganados por las unidades completas compradas."""
    return int(float(quantity)) * int(promotion["points_per_unit"])


def _money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def line_discount(
    quantity: float,
    unit_price: float,
    category_quantity: float,
    promotions: Sequence[Mapping[str, Any]],
) -> tuple[float, Mapping[str, Any] | None]:
    """Elige la primera regla de precio aplicable y calcula el descuento de línea.

    La prioridad respeta el orden de promociones activas usado por el caso de
    venta: descuento porcentual, segundo a mitad de precio y precio de mayoreo.
    """
    qty = float(quantity)
    price = float(unit_price)
    subtotal = _money(qty * price)
    for promotion in promotions:
        kind = promotion["type"]
        if kind == "discount":
            discount = _money(subtotal * float(promotion["discount_percent"]) / 100)
            return discount, promotion
        if kind == "half_second" and qty >= 2:
            discount = _money((int(qty) // 2) * price * 0.5)
            return discount, promotion
        if (
            kind == "wholesale"
            and float(category_quantity) >= float(promotion["min_qty"])
        ):
            wholesale_price = float(promotion["wholesale_price"])
            if 0 < wholesale_price < price:
                discount = _money(qty * (price - wholesale_price))
                return discount, promotion
    return 0.0, None
