from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import quote

from sqlmodel import Session, select

from gastroflow.domain.enums import EstadoPedido, FormaPago, ReglaPrecioCombo, TipoPromocion
from gastroflow.domain.errors import ValidationError
from gastroflow.domain.order_state import assert_valid_order_transition
from gastroflow.models import (
    Categoria,
    Cliente,
    ComboRegla,
    Pedido,
    PedidoItem,
    PedidoRead,
    PrecioMayoristaProducto,
    Producto,
    Promocion,
    PromocionProducto,
    ReglaMayorista,
    UsuarioRead,
    ZonaEnvio,
)
from gastroflow.services.auth import AuthService
from gastroflow.services.codes import next_business_code

MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class OrderItemInput:
    producto_id: int
    cantidad: int
    producto_combo_id: int | None = None


@dataclass(frozen=True)
class PublicOrderInput:
    nombre_apellido: str
    telefono: str
    fecha_entrega: date
    direccion_delivery: str
    forma_pago: FormaPago
    items: list[OrderItemInput]
    zona_envio_id: int | None = None
    direccion_lat: Decimal | None = None
    direccion_lng: Decimal | None = None
    observaciones: str | None = None


@dataclass(frozen=True)
class CreatedOrderResult:
    pedido: PedidoRead
    whatsapp_url: str | None


@dataclass(frozen=True)
class PricedItem:
    item: OrderItemInput
    precio_unitario: Decimal
    requiere_confirmacion: bool


class OrderService:
    def __init__(self, session: Session):
        self.session = session

    def create_public_order(self, data: PublicOrderInput) -> CreatedOrderResult:
        if not data.items:
            raise ValidationError("El pedido debe tener al menos un item.")

        cliente = self._upsert_cliente(data.nombre_apellido, data.telefono)
        codigo = next_business_code(self.session, "pedido_codigo_seq", "PED")
        costo_envio = self._snapshot_delivery_cost(data.zona_envio_id)
        priced_items = self._price_items(data.items)
        monto_items = sum(
            (priced_item.precio_unitario * priced_item.item.cantidad for priced_item in priced_items),
            Decimal("0"),
        )
        monto_total = self._money(monto_items + costo_envio)
        requires_confirmation = any(item.requiere_confirmacion for item in priced_items)
        estado = (
            EstadoPedido.PENDIENTE_CONFIRMACION
            if requires_confirmation
            else EstadoPedido.PEDIDO
        )

        pedido = Pedido(
            codigo=codigo,
            fecha_entrega=data.fecha_entrega,
            cliente_id=cliente.id or 0,
            direccion_delivery=data.direccion_delivery.strip(),
            direccion_lat=data.direccion_lat,
            direccion_lng=data.direccion_lng,
            zona_envio_id=data.zona_envio_id,
            costo_envio=costo_envio,
            forma_pago=data.forma_pago,
            estado=estado,
            observaciones=data.observaciones,
            monto_total=monto_total,
        )
        self.session.add(pedido)
        self.session.flush()

        for priced_item in priced_items:
            self.session.add(
                PedidoItem(
                    pedido_id=pedido.id or 0,
                    producto_id=priced_item.item.producto_id,
                    producto_combo_id=priced_item.item.producto_combo_id,
                    cantidad=priced_item.item.cantidad,
                    precio_unitario=priced_item.precio_unitario,
                )
            )

        self.session.commit()
        self.session.refresh(pedido)
        whatsapp_url = self._build_whatsapp_url(pedido, data, priced_items) if requires_confirmation else None
        return CreatedOrderResult(pedido=self._to_read(pedido), whatsapp_url=whatsapp_url)

    def transition_order(
        self,
        pedido_id: int,
        next_state: EstadoPedido,
        current_user: UsuarioRead,
    ) -> PedidoRead:
        AuthService(self.session).require_owner_or_admin(current_user)
        pedido = self.session.get(Pedido, pedido_id)
        if pedido is None:
            raise ValidationError("Pedido inexistente.")

        assert_valid_order_transition(pedido.estado, next_state)
        pedido.estado = next_state
        self.session.add(pedido)
        self.session.commit()
        self.session.refresh(pedido)
        return self._to_read(pedido)

    def _upsert_cliente(self, nombre_apellido: str, telefono: str) -> Cliente:
        normalized_phone = normalize_phone(telefono)
        if not normalized_phone:
            raise ValidationError("El telefono del cliente es obligatorio.")

        cliente = self.session.exec(
            select(Cliente).where(Cliente.telefono == normalized_phone)
        ).first()
        if cliente is None:
            cliente = Cliente(
                nombre_apellido=nombre_apellido.strip(),
                telefono=normalized_phone,
            )
            self.session.add(cliente)
            self.session.flush()
        else:
            cliente.nombre_apellido = nombre_apellido.strip() or cliente.nombre_apellido
            self.session.add(cliente)
            self.session.flush()
        return cliente

    def _snapshot_delivery_cost(self, zona_envio_id: int | None) -> Decimal:
        if zona_envio_id is None:
            return Decimal("0.00")

        zona = self.session.get(ZonaEnvio, zona_envio_id)
        if zona is None:
            raise ValidationError("Zona de envio inexistente.")
        return self._money(zona.costo)

    def _price_items(self, items: list[OrderItemInput]) -> list[PricedItem]:
        products = self._load_products(items)
        wholesale_prices = self._eligible_wholesale_prices(items, products)
        promotional_prices = self._eligible_promotional_prices(items)

        priced_items: list[PricedItem] = []
        for item in items:
            if item.cantidad <= 0:
                raise ValidationError("La cantidad debe ser mayor a cero.")
            product = products[item.producto_id]
            base_price = wholesale_prices.get(item.producto_id)
            if base_price is None:
                base_price = promotional_prices.get(item.producto_id, product.precio)

            requires_confirmation = False
            unit_price = base_price
            if item.producto_combo_id is not None:
                combo_product = products[item.producto_combo_id]
                combo_base_price = wholesale_prices.get(item.producto_combo_id)
                if combo_base_price is None:
                    combo_base_price = promotional_prices.get(item.producto_combo_id, combo_product.precio)
                combo_rule = self._get_combo_rule(product.id or 0, combo_product.id or 0)
                unit_price = self._combo_price(combo_rule, base_price, combo_base_price)
                requires_confirmation = combo_rule.requiere_confirmacion

            priced_items.append(
                PricedItem(
                    item=item,
                    precio_unitario=self._money(unit_price),
                    requiere_confirmacion=requires_confirmation,
                )
            )
        return priced_items

    def _load_products(self, items: list[OrderItemInput]) -> dict[int, Producto]:
        product_ids = {item.producto_id for item in items}
        product_ids.update(item.producto_combo_id for item in items if item.producto_combo_id is not None)
        products = self.session.exec(select(Producto).where(Producto.id.in_(product_ids))).all()
        product_by_id = {product.id or 0: product for product in products}
        missing = product_ids - set(product_by_id)
        if missing:
            raise ValidationError(f"Productos inexistentes: {sorted(missing)}.")
        return product_by_id

    def _eligible_wholesale_prices(
        self,
        items: list[OrderItemInput],
        products: dict[int, Producto],
    ) -> dict[int, Decimal]:
        quantities_by_category: dict[int, int] = {}
        for item in items:
            product = products[item.producto_id]
            quantities_by_category[product.categoria_id] = (
                quantities_by_category.get(product.categoria_id, 0) + item.cantidad
            )

        prices: dict[int, Decimal] = {}
        for category_id, quantity in quantities_by_category.items():
            rule = self.session.exec(
                select(ReglaMayorista).where(
                    ReglaMayorista.categoria_id == category_id,
                    ReglaMayorista.activa == True,  # noqa: E712
                )
            ).first()
            if rule is None:
                continue
            if quantity < rule.cantidad_minima_total:
                continue

            rows = self.session.exec(
                select(PrecioMayoristaProducto).where(
                    PrecioMayoristaProducto.regla_mayorista_id == rule.id
                )
            ).all()
            for row in rows:
                prices[row.producto_id] = row.precio_unitario_mayorista
        return prices

    def _eligible_promotional_prices(self, items: list[OrderItemInput]) -> dict[int, Decimal]:
        quantities_by_product = {
            item.producto_id: sum(i.cantidad for i in items if i.producto_id == item.producto_id)
            for item in items
        }
        promotions = self.session.exec(
            select(Promocion).where(
                Promocion.activa == True,  # noqa: E712
                Promocion.tipo == TipoPromocion.PRECIO_UNITARIO_POR_CANTIDAD,
            )
        ).all()

        prices: dict[int, Decimal] = {}
        for promotion in promotions:
            links = self.session.exec(
                select(PromocionProducto).where(PromocionProducto.promocion_id == promotion.id)
            ).all()
            eligible_product_ids = {link.producto_id for link in links}
            eligible_quantity = sum(
                quantity
                for product_id, quantity in quantities_by_product.items()
                if product_id in eligible_product_ids
            )
            if eligible_quantity < promotion.cantidad_minima:
                continue
            for product_id in eligible_product_ids:
                current_price = prices.get(product_id)
                if current_price is None or promotion.precio_unitario_promocional < current_price:
                    prices[product_id] = promotion.precio_unitario_promocional
        return prices

    def _get_combo_rule(self, product_a_id: int, product_b_id: int) -> ComboRegla:
        combo_rule = self.session.exec(
            select(ComboRegla).where(
                (
                    (ComboRegla.producto_a_id == product_a_id)
                    & (ComboRegla.producto_b_id == product_b_id)
                )
                | (
                    (ComboRegla.producto_a_id == product_b_id)
                    & (ComboRegla.producto_b_id == product_a_id)
                )
            )
        ).first()
        if combo_rule is None:
            raise ValidationError("La combinacion de productos no esta habilitada.")
        return combo_rule

    def _combo_price(
        self,
        combo_rule: ComboRegla,
        product_a_price: Decimal,
        product_b_price: Decimal,
    ) -> Decimal:
        if combo_rule.regla_precio == ReglaPrecioCombo.MAYOR_VALOR:
            return max(product_a_price, product_b_price)
        if combo_rule.regla_precio == ReglaPrecioCombo.PROMEDIO:
            return (product_a_price + product_b_price) / Decimal("2")
        if combo_rule.precio_fijo_combo is None:
            raise ValidationError("El combo con precio fijo no tiene precio configurado.")
        return combo_rule.precio_fijo_combo

    def _build_whatsapp_url(
        self,
        pedido: Pedido,
        data: PublicOrderInput,
        priced_items: list[PricedItem],
    ) -> str:
        lines = [
            f"Pedido {pedido.codigo} requiere confirmacion",
            f"Cliente: {data.nombre_apellido}",
            f"Telefono: {normalize_phone(data.telefono)}",
            f"Entrega: {data.fecha_entrega.isoformat()}",
            f"Total: {pedido.monto_total}",
        ]
        for priced_item in priced_items:
            lines.append(
                f"- Producto {priced_item.item.producto_id}"
                f"{' + ' + str(priced_item.item.producto_combo_id) if priced_item.item.producto_combo_id else ''}"
                f" x{priced_item.item.cantidad}: {priced_item.precio_unitario}"
            )
        return f"https://wa.me/?text={quote(chr(10).join(lines))}"

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(MONEY_QUANT)

    @staticmethod
    def _to_read(pedido: Pedido) -> PedidoRead:
        return PedidoRead(
            id=pedido.id or 0,
            codigo=pedido.codigo,
            fecha_entrega=pedido.fecha_entrega,
            cliente_id=pedido.cliente_id,
            direccion_delivery=pedido.direccion_delivery,
            direccion_lat=pedido.direccion_lat,
            direccion_lng=pedido.direccion_lng,
            zona_envio_id=pedido.zona_envio_id,
            costo_envio=pedido.costo_envio,
            forma_pago=pedido.forma_pago,
            estado=pedido.estado,
            observaciones=pedido.observaciones,
            monto_total=pedido.monto_total,
            created_at=pedido.created_at,
            updated_at=pedido.updated_at,
        )


def normalize_phone(phone: str) -> str:
    normalized = "".join(char for char in phone.strip() if char.isdigit() or char == "+")
    if normalized.startswith("00"):
        normalized = f"+{normalized[2:]}"
    return normalized
