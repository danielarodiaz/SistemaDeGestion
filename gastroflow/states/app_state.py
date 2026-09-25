from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import reflex as rx
from sqlmodel import Session, select

from gastroflow.data.database import engine
from gastroflow.domain.enums import EstadoPedido, FormaPago, RolUsuario
from gastroflow.domain.errors import DomainError
from gastroflow.models import Categoria, Cliente, Gasto, Pedido, Producto, UsuarioRead, ZonaEnvio
from gastroflow.services import (
    AdminCrudService,
    AuthService,
    CRUD_TABLES,
    ExpenseInput,
    ExpenseService,
    OrderItemInput,
    OrderService,
    PublicOrderInput,
)

MONEY_QUANT = Decimal("0.01")
STORE_NAME = os.getenv("STORE_NAME", "")
PIZZERIA_WHATSAPP_PHONE = os.getenv("PIZZERIA_WHATSAPP_PHONE", "")
TRANSFER_TITULAR = os.getenv("TRANSFER_TITULAR", "")
TRANSFER_ALIAS = os.getenv("TRANSFER_ALIAS", "")


def _display(value: Any) -> Any:
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


def _display_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: _display(value) for key, value in record.items()}


def _display_record_row(record: dict[str, Any]) -> dict[str, Any]:
    display_record = _display_record(record)
    return {
        "id": str(display_record.get("id", "")),
        "display": json.dumps(display_record, ensure_ascii=False, default=str),
    }


def _money_text(value: Decimal | str | int) -> str:
    amount = Decimal(str(value)).quantize(MONEY_QUANT)
    return f"{amount:.2f}".replace(".", ",")


def _parse_delivery_date(value: str) -> date:
    clean = value.strip()
    if "-" in clean:
        return date.fromisoformat(clean)
    day, month, year = clean.split("/")
    return date(int(year), int(month), int(day))


def _mask_date(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())[:8]
    if len(digits) <= 2:
        return digits
    if len(digits) <= 4:
        return f"{digits[:2]}/{digits[2:]}"
    return f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"


def _mask_time(value: str) -> str:
    digits = "".join(char for char in value if char.isdigit())[:4]
    if len(digits) <= 2:
        return digits
    return f"{digits[:2]}:{digits[2:]}"


def _validate_time(value: str) -> None:
    hour, minute = value.split(":")
    if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
        raise ValueError("Ingresa un horario valido con formato HH:MM.")


class AuthState(rx.State):
    username: str = ""
    password: str = ""
    user_id: int = 0
    role: str = ""
    message: str = ""

    @rx.var
    def is_authenticated(self) -> bool:
        return self.user_id > 0

    @rx.var
    def is_admin(self) -> bool:
        return self.role == RolUsuario.ADMIN.value

    def current_user(self) -> UsuarioRead:
        role = RolUsuario(self.role or RolUsuario.DUENO.value)
        return UsuarioRead(
            id=self.user_id,
            username=self.username,
            rol=role,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def login(self) -> rx.event.EventSpec | None:
        try:
            with Session(engine) as session:
                user = AuthService(session).authenticate(self.username, self.password)
            self.user_id = user.id
            self.username = user.username
            self.role = user.rol.value
            self.password = ""
            self.message = "Sesion iniciada."
            return rx.redirect("/pedidos")
        except DomainError as exc:
            self.message = str(exc)
            return None

    def logout(self) -> rx.event.EventSpec:
        self.username = ""
        self.password = ""
        self.user_id = 0
        self.role = ""
        self.message = "Sesion cerrada."
        return rx.redirect("/login")


class PublicOrderState(rx.State):
    categories: list[dict[str, Any]] = []
    products: list[dict[str, Any]] = []
    visible_products: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    cart: list[dict[str, Any]] = []
    selected_product: dict[str, Any] = {}
    selected_category_id: str = ""
    view: str = "categories"
    detail_quantity: str = "1"
    nombre_apellido: str = ""
    telefono: str = ""
    fecha_entrega: str = ""
    horario_entrega: str = ""
    direccion_delivery: str = ""
    delivery_mode: str = "retiro"
    zona_envio_id: str = ""
    selected_zone_name: str = ""
    selected_zone_cost: str = "0,00"
    forma_pago: str = FormaPago.EFECTIVO.value
    observaciones: str = ""
    cart_total: str = "0.00"
    cart_total_display: str = "0,00"
    order_total_display: str = "0,00"
    message: str = ""

    def load_catalog(self) -> None:
        with Session(engine) as session:
            categories = session.exec(select(Categoria)).all()
            products = session.exec(select(Producto)).all()
            zones = session.exec(select(ZonaEnvio)).all()

        category_names = {category.id: category.nombre for category in categories}
        product_count_by_category: dict[int, int] = {}
        for product in products:
            product_count_by_category[product.categoria_id] = product_count_by_category.get(product.categoria_id, 0) + 1

        self.categories = [
            {
                "id": category.id,
                "codigo": category.codigo,
                "nombre": category.nombre,
                "total": product_count_by_category.get(category.id or 0, 0),
            }
            for category in categories
        ]
        self.products = [
            {
                "id": product.id,
                "categoria_id": product.categoria_id,
                "categoria": category_names.get(product.categoria_id, ""),
                "codigo": product.codigo,
                "nombre": product.nombre,
                "precio": str(product.precio),
                "descripcion": product.descripcion or "Producto artesanal listo para sumar a tu pedido.",
                "foto": (product.fotos or [""])[0] if product.fotos else "",
            }
            for product in products
        ]
        self.zones = [
            {
                "id": zone.id,
                "id_str": str(zone.id),
                "nombre": zone.nombre,
                "costo": str(zone.costo),
                "costo_display": _money_text(zone.costo),
            }
            for zone in zones
        ]
        if not self.view:
            self.view = "categories"

    def show_categories(self) -> None:
        self.view = "categories"
        self.selected_category_id = ""
        self.visible_products = []
        self.selected_product = {}
        self.message = ""

    def show_category(self, category_id: int) -> None:
        self.selected_category_id = str(category_id)
        self.visible_products = [
            product for product in self.products if str(product["categoria_id"]) == str(category_id)
        ]
        self.selected_product = {}
        self.view = "products"
        self.message = ""

    def open_product(self, product_id: int) -> None:
        product = next((item for item in self.products if str(item["id"]) == str(product_id)), {})
        self.selected_product = product
        self.detail_quantity = "1"
        self.view = "detail"
        self.message = ""

    def add_selected_to_cart(self) -> None:
        if not self.selected_product:
            self.message = "Selecciona un producto."
            return
        try:
            quantity = int(self.detail_quantity)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            self.message = "La cantidad debe ser mayor a cero."
            return

        product_id = int(self.selected_product["id"])
        cart = list(self.cart)
        for index, item in enumerate(cart):
            if int(item["producto_id"]) == product_id:
                item["cantidad"] = int(item["cantidad"]) + quantity
                cart[index] = item
                break
        else:
            price = Decimal(str(self.selected_product["precio"]))
            cart.append(
                {
                    "producto_id": product_id,
                    "nombre": self.selected_product["nombre"],
                    "categoria": self.selected_product["categoria"],
                    "precio": str(price),
                    "precio_display": _money_text(price),
                    "cantidad": quantity,
                    "subtotal": str(price * Decimal(quantity)),
                    "subtotal_display": _money_text(price * Decimal(quantity)),
                    "base_subtotal_display": _money_text(price * Decimal(quantity)),
                    "discount": "0.00",
                    "discount_display": "0,00",
                    "promo_label": "",
                    "foto": self.selected_product.get("foto", ""),
                }
            )
        self.cart = cart
        self._refresh_cart_total()
        self.message = "Producto agregado al pedido."
        self.view = "products"

    def remove_cart_item(self, product_id: int) -> None:
        self.cart = [item for item in self.cart if int(item["producto_id"]) != int(product_id)]
        self._refresh_cart_total()
        self.message = ""

    def show_cart(self) -> None:
        self.view = "cart"
        self.message = ""

    def set_fecha_entrega(self, value: str) -> None:
        self.fecha_entrega = _mask_date(value)

    def set_horario_entrega(self, value: str) -> None:
        self.horario_entrega = _mask_time(value)

    def set_delivery_mode(self, value: str) -> None:
        self.delivery_mode = value
        if value == "retiro":
            self.direccion_delivery = ""
            self.zona_envio_id = ""
            self.selected_zone_name = ""
            self.selected_zone_cost = "0,00"
        self._refresh_cart_total()

    def select_zone(self, zone_id: int) -> None:
        selected = next((zone for zone in self.zones if str(zone["id"]) == str(zone_id)), {})
        self.zona_envio_id = str(zone_id)
        self.selected_zone_name = selected.get("nombre", "")
        self.selected_zone_cost = selected.get("costo_display", "0,00")
        self._refresh_cart_total()

    def set_forma_pago(self, value: str) -> None:
        self.forma_pago = value

    def submit_order(self) -> rx.event.EventSpec | None:
        try:
            if not self.cart:
                raise ValueError("Tu pedido esta vacio.")
            delivery_date = _parse_delivery_date(self.fecha_entrega)
            _validate_time(self.horario_entrega)
            if self.delivery_mode == "delivery" and not self.zona_envio_id:
                raise ValueError("Selecciona una zona de envio.")
            items = [
                OrderItemInput(
                    producto_id=int(item["producto_id"]),
                    cantidad=int(item["cantidad"]),
                )
                for item in self.cart
            ]
            payload = PublicOrderInput(
                nombre_apellido=self.nombre_apellido,
                telefono=self.telefono,
                fecha_entrega=delivery_date,
                direccion_delivery=self.direccion_delivery if self.delivery_mode == "delivery" else "Retiro en el local",
                zona_envio_id=int(self.zona_envio_id) if self.delivery_mode == "delivery" and self.zona_envio_id else None,
                forma_pago=FormaPago(self.forma_pago),
                observaciones=self.observaciones or None,
                items=items,
            )
            with Session(engine) as session:
                result = OrderService(session).create_public_order(payload)
            whatsapp_url = self._build_whatsapp_url(result.pedido.codigo, result.pedido.monto_total)
            self.message = "Pedido creado. Te llevamos a WhatsApp para enviar el resumen."
            return rx.redirect(whatsapp_url, is_external=True)
        except Exception as exc:
            self.message = str(exc)
            return None

    def _refresh_cart_total(self) -> None:
        cart = [dict(item) for item in self.cart]
        if cart:
            try:
                inputs = [
                    OrderItemInput(producto_id=int(item["producto_id"]), cantidad=int(item["cantidad"]))
                    for item in cart
                ]
                with Session(engine) as session:
                    priced_items = OrderService(session)._price_items(inputs)
                for cart_item, priced_item in zip(cart, priced_items):
                    base_unit = Decimal(str(cart_item["precio"]))
                    final_unit = Decimal(str(priced_item.precio_unitario))
                    quantity = Decimal(str(cart_item["cantidad"]))
                    base_subtotal = base_unit * quantity
                    subtotal = final_unit * quantity
                    discount = base_subtotal - subtotal
                    cart_item["precio_final"] = str(final_unit)
                    cart_item["subtotal"] = str(subtotal)
                    cart_item["subtotal_display"] = _money_text(subtotal)
                    cart_item["base_subtotal_display"] = _money_text(base_subtotal)
                    cart_item["discount"] = str(discount)
                    cart_item["discount_display"] = _money_text(discount)
                    cart_item["promo_label"] = (
                        f"Promo aplicada: $-{_money_text(discount)}" if discount > 0 else ""
                    )
            except Exception:
                for cart_item in cart:
                    subtotal = Decimal(str(cart_item["precio"])) * Decimal(str(cart_item["cantidad"]))
                    cart_item["subtotal"] = str(subtotal)
                    cart_item["subtotal_display"] = _money_text(subtotal)
                    cart_item["base_subtotal_display"] = _money_text(subtotal)
                    cart_item["discount"] = "0.00"
                    cart_item["discount_display"] = "0,00"
                    cart_item["promo_label"] = ""

        items_total = sum((Decimal(str(item["subtotal"])) for item in cart), Decimal("0.00"))
        shipping = self._selected_shipping_cost()
        order_total = items_total + shipping
        self.cart = cart
        self.cart_total = str(items_total.quantize(MONEY_QUANT))
        self.cart_total_display = _money_text(items_total)
        self.order_total_display = _money_text(order_total)

    def _selected_shipping_cost(self) -> Decimal:
        if self.delivery_mode != "delivery" or not self.zona_envio_id:
            return Decimal("0.00")
        selected = next((zone for zone in self.zones if str(zone["id"]) == self.zona_envio_id), None)
        return Decimal(str(selected["costo"])) if selected else Decimal("0.00")

    def _build_whatsapp_url(self, pedido_codigo: str, total: Decimal) -> str:
        now = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%d/%m/%y - %H:%Mhs")
        delivery_label = "Delivery" if self.delivery_mode == "delivery" else "Retiro del local"
        lines = [
            "¡Hola! Te paso el resumen de mi pedido",
            "",
            f"Pedido: #{pedido_codigo}",
            f"Tienda: {STORE_NAME}",
            f"Fecha: {now}",
            f"Nombre: {self.nombre_apellido}",
                f"Telefono: {self.telefono}",
                f"Horario ideal de entrega: {self.horario_entrega}hs",
                "",
                f"Forma de pago: {'Transferencia' if self.forma_pago == FormaPago.TRANSFERENCIA.value else 'Efectivo'}",
        ]
        if self.forma_pago == FormaPago.TRANSFERENCIA.value:
            lines.extend(
                [
                    "",
                    "Datos para la transferencia",
                    f"Titular: {TRANSFER_TITULAR}",
                    f"Alias: {TRANSFER_ALIAS}",
                    "Realiza la transferencia y luego envianos el comprobante por este chat.",
                    "Esperar confirmacion antes de transferir.",
                ]
            )
        lines.extend(
            [
                "",
                f"Total: ${_money_text(total)}",
                "",
                f"Entrega: {delivery_label}",
            ]
        )
        if self.delivery_mode == "delivery":
            lines.append(f"Direccion: {self.direccion_delivery}")
            lines.append(f"Zona: {self.selected_zone_name}")
        if self.observaciones:
            lines.append(f"Referencia/observaciones: {self.observaciones}")
        lines.extend(["", "Mi pedido es", ""])
        categories = []
        for item in self.cart:
            category = item.get("categoria", "Productos")
            if category not in categories:
                categories.append(category)
        for category in categories:
            lines.append(f"{category.upper()} ({category.upper()})")
            for item in self.cart:
                if item.get("categoria", "Productos") != category:
                    continue
                lines.append(
                    f"{item['cantidad']}x {item['nombre']}: ${item['subtotal_display']}"
                )
                if item.get("promo_label"):
                    lines.append(item["promo_label"])
        lines.extend(
            [
                "",
                f"Subtotal: ${self.cart_total_display}",
                f"Costo de envio: +${self.selected_zone_cost if self.delivery_mode == 'delivery' else '0,00'}",
                f"TOTAL: ${_money_text(total)}",
                "",
                "Espero tu respuesta para confirmar mi pedido",
            ]
        )
        phone = "".join(char for char in PIZZERIA_WHATSAPP_PHONE if char.isdigit())
        target = f"https://wa.me/{phone}" if phone else "https://wa.me/"
        return f"{target}?text={quote(chr(10).join(lines))}"


class OperationsState(rx.State):
    orders: list[dict[str, Any]] = []
    message: str = ""

    def load_orders(self) -> None:
        with Session(engine) as session:
            pedidos = session.exec(select(Pedido)).all()
            clientes = {cliente.id: cliente for cliente in session.exec(select(Cliente)).all()}
        self.orders = [
            {
                "id": pedido.id,
                "codigo": pedido.codigo,
                "cliente": clientes.get(pedido.cliente_id).nombre_apellido if clientes.get(pedido.cliente_id) else "",
                "estado": pedido.estado.value,
                "total": str(pedido.monto_total),
                "fecha": str(pedido.fecha_entrega),
            }
            for pedido in pedidos
        ]

    async def transition(self, pedido_id: int, next_state: str) -> None:
        auth = await self.get_state(AuthState)
        if not auth.user_id:
            self.message = "Inicia sesion para operar pedidos."
            return
        try:
            with Session(engine) as session:
                OrderService(session).transition_order(
                    pedido_id=pedido_id,
                    next_state=EstadoPedido(next_state),
                    current_user=auth.current_user(),
                )
            self.message = "Estado actualizado."
            self.load_orders()
        except DomainError as exc:
            self.message = str(exc)


class ExpenseState(rx.State):
    fecha: str = ""
    motivo_nombre: str = ""
    marca_nombre: str = ""
    cantidad: str = "1"
    unidad_medida: str = "kg"
    precio: str = "0"
    lugar_texto: str = ""
    message: str = ""
    expenses: list[dict[str, Any]] = []

    def load_expenses(self) -> None:
        with Session(engine) as session:
            gastos = session.exec(select(Gasto)).all()
        self.expenses = [
            {
                "codigo": gasto.codigo,
                "fecha": str(gasto.fecha),
                "cantidad": str(gasto.cantidad),
                "unidad": gasto.unidad_medida,
                "precio": str(gasto.precio),
                "lugar": gasto.lugar_texto,
            }
            for gasto in gastos
        ]

    async def submit_expense(self) -> None:
        auth = await self.get_state(AuthState)
        if not auth.user_id:
            self.message = "Inicia sesion para cargar gastos."
            return
        try:
            payload = ExpenseInput(
                fecha=date.fromisoformat(self.fecha),
                motivo_nombre=self.motivo_nombre,
                marca_nombre=self.marca_nombre,
                cantidad=Decimal(self.cantidad),
                unidad_medida=self.unidad_medida,
                precio=Decimal(self.precio),
                lugar_texto=self.lugar_texto,
            )
            with Session(engine) as session:
                gasto = ExpenseService(session).create_expense(payload, auth.current_user())
            self.message = f"Gasto {gasto.codigo} creado."
            self.load_expenses()
        except Exception as exc:
            self.message = str(exc)


class AdminCrudState(rx.State):
    table_name: str = "categoria"
    tables: list[str] = list(CRUD_TABLES.keys())
    records: list[dict[str, Any]] = []
    payload_json: str = "{}"
    selected_id: str = ""
    message: str = ""

    async def load_records(self) -> None:
        auth = await self.get_state(AuthState)
        if auth.role != RolUsuario.ADMIN.value:
            self.message = "Solo Admin puede administrar datos."
            return
        try:
            with Session(engine) as session:
                records = AdminCrudService(session).list_records(self.table_name, auth.current_user())
            self.records = [_display_record_row(record) for record in records]
            self.message = f"{len(self.records)} registros."
        except Exception as exc:
            self.message = str(exc)

    def set_table(self, table_name: str) -> None:
        self.table_name = table_name
        self.records = []
        self.selected_id = ""
        self.payload_json = "{}"

    async def create_record(self) -> None:
        await self._save_record(create=True)

    async def update_record(self) -> None:
        await self._save_record(create=False)

    async def delete_record(self) -> None:
        auth = await self.get_state(AuthState)
        if auth.role != RolUsuario.ADMIN.value:
            self.message = "Solo Admin puede borrar datos."
            return
        try:
            with Session(engine) as session:
                AdminCrudService(session).delete_record(self.table_name, int(self.selected_id), auth.current_user())
            self.message = "Registro borrado."
            await self.load_records()
        except Exception as exc:
            self.message = str(exc)

    async def _save_record(self, *, create: bool) -> None:
        auth = await self.get_state(AuthState)
        if auth.role != RolUsuario.ADMIN.value:
            self.message = "Solo Admin puede guardar datos."
            return
        try:
            data = json.loads(self.payload_json)
            with Session(engine) as session:
                service = AdminCrudService(session)
                if create:
                    record = service.create_record(self.table_name, data, auth.current_user())
                else:
                    record = service.update_record(self.table_name, int(self.selected_id), data, auth.current_user())
            self.message = f"Guardado: {_display_record(record)}"
            await self.load_records()
        except Exception as exc:
            self.message = str(exc)
