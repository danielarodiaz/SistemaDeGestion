from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, select

from gastroflow.data.database import engine
from gastroflow.domain.enums import ReglaPrecioCombo, TipoPromocion, UnidadVenta
from gastroflow.models import (
    Categoria,
    ComboRegla,
    PrecioMayoristaProducto,
    Producto,
    Promocion,
    PromocionProducto,
    ReglaMayorista,
    ZonaEnvio,
)

SEED_PATH = Path(__file__).resolve().parents[1] / "gastroflow" / "seed" / "catalog_seed.json"


def first_or_create(session: Session, model: type, lookup: dict, values: dict):
    statement = select(model)
    for field, value in lookup.items():
        statement = statement.where(getattr(model, field) == value)
    instance = session.exec(statement).first()
    if instance is not None:
        return instance

    instance = model(**lookup, **values)
    session.add(instance)
    session.flush()
    return instance


def main() -> None:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    with Session(engine) as session:
        categories: dict[str, Categoria] = {}
        products: dict[str, Producto] = {}

        for row in data["categories"]:
            categories[row["codigo"]] = first_or_create(
                session,
                Categoria,
                {"codigo": row["codigo"]},
                {"nombre": row["nombre"]},
            )

        for row in data["products"]:
            products[row["codigo"]] = first_or_create(
                session,
                Producto,
                {"codigo": row["codigo"]},
                {
                    "categoria_id": categories[row["categoria_codigo"]].id,
                    "nombre": row["nombre"],
                    "descripcion": row["descripcion"],
                    "fotos": row["fotos"],
                    "precio": Decimal(row["precio"]),
                    "unidad_venta": UnidadVenta[row["unidad_venta"]],
                },
            )

        for row in data["promotions"]:
            promotion = first_or_create(
                session,
                Promocion,
                {"codigo": row["codigo"]},
                {
                    "nombre": row["nombre"],
                    "tipo": TipoPromocion[row["tipo"]],
                    "cantidad_minima": row["cantidad_minima"],
                    "precio_unitario_promocional": Decimal(row["precio_unitario_promocional"]),
                    "activa": row["activa"],
                },
            )
            for product_code in row["productos_elegibles"]:
                first_or_create(
                    session,
                    PromocionProducto,
                    {
                        "promocion_id": promotion.id,
                        "producto_id": products[product_code].id,
                    },
                    {},
                )

        for row in data["wholesale_rules"]:
            rule = first_or_create(
                session,
                ReglaMayorista,
                {"codigo": row["codigo"]},
                {
                    "categoria_id": categories[row["categoria_codigo"]].id,
                    "nombre": row["nombre"],
                    "cantidad_minima_total": row["cantidad_minima_total"],
                    "activa": row["activa"],
                },
            )
            for price_row in row["product_prices"]:
                first_or_create(
                    session,
                    PrecioMayoristaProducto,
                    {
                        "regla_mayorista_id": rule.id,
                        "producto_id": products[price_row["producto_codigo"]].id,
                    },
                    {"precio_unitario_mayorista": Decimal(price_row["precio_unitario_mayorista"])},
                )

        for row in data["delivery_zones"]:
            first_or_create(
                session,
                ZonaEnvio,
                {"nombre": row["nombre"]},
                {"costo": Decimal(row["costo"])},
            )

        for row in data["combo_rules"]:
            first_or_create(
                session,
                ComboRegla,
                {
                    "producto_a_id": products[row["producto_a_codigo"]].id,
                    "producto_b_id": products[row["producto_b_codigo"]].id,
                },
                {
                    "requiere_confirmacion": row["requiere_confirmacion"],
                    "regla_precio": ReglaPrecioCombo[row["regla_precio"]],
                    "precio_fijo_combo": (
                        Decimal(row["precio_fijo_combo"])
                        if row["precio_fijo_combo"] is not None
                        else None
                    ),
                },
            )

        session.commit()

    print("Catalogo inicial cargado.")


if __name__ == "__main__":
    main()
