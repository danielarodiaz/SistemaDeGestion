from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import reflex as rx
from sqlmodel import Session, select

from gastroflow.data.database import engine
from gastroflow.domain.enums import EstadoPedido, FormaPago, RolUsuario
from gastroflow.domain.errors import DomainError
from gastroflow.models import Cliente, Gasto, Pedido, Producto, UsuarioRead, ZonaEnvio
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
        "id": display_record.get("id", ""),
        "display": json.dumps(display_record, ensure_ascii=False, default=str),
    }


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

    def login(self) -> None:
        try:
            with Session(engine) as session:
                user = AuthService(session).authenticate(self.username, self.password)
            self.user_id = user.id
            self.username = user.username
            self.role = user.rol.value
            self.password = ""
            self.message = "Sesion iniciada."
        except DomainError as exc:
            self.message = str(exc)

    def logout(self) -> None:
        self.username = ""
        self.password = ""
        self.user_id = 0
        self.role = ""
        self.message = "Sesion cerrada."


class PublicOrderState(rx.State):
    products: list[dict[str, Any]] = []
    zones: list[dict[str, Any]] = []
    selected_product_id: str = ""
    selected_combo_id: str = ""
    quantity: str = "1"
    nombre_apellido: str = ""
    telefono: str = ""
    fecha_entrega: str = ""
    direccion_delivery: str = "Retiro en el local"
    zona_envio_id: str = ""
    forma_pago: str = FormaPago.EFECTIVO.value
    observaciones: str = ""
    message: str = ""

    def load_catalog(self) -> None:
        with Session(engine) as session:
            products = session.exec(select(Producto)).all()
            zones = session.exec(select(ZonaEnvio)).all()
        self.products = [
            {
                "id": product.id,
                "nombre": product.nombre,
                "precio": str(product.precio),
                "descripcion": product.descripcion or "",
            }
            for product in products
        ]
        self.zones = [{"id": zone.id, "nombre": zone.nombre, "costo": str(zone.costo)} for zone in zones]

    def select_product(self, product_id: int) -> None:
        self.selected_product_id = str(product_id)

    def select_combo(self, product_id: int) -> None:
        self.selected_combo_id = "" if self.selected_combo_id == str(product_id) else str(product_id)

    def submit_order(self) -> None:
        try:
            if not self.selected_product_id:
                raise ValueError("Selecciona un producto.")
            item = OrderItemInput(
                producto_id=int(self.selected_product_id),
                producto_combo_id=int(self.selected_combo_id) if self.selected_combo_id else None,
                cantidad=int(self.quantity),
            )
            payload = PublicOrderInput(
                nombre_apellido=self.nombre_apellido,
                telefono=self.telefono,
                fecha_entrega=date.fromisoformat(self.fecha_entrega),
                direccion_delivery=self.direccion_delivery,
                zona_envio_id=int(self.zona_envio_id) if self.zona_envio_id else None,
                forma_pago=FormaPago(self.forma_pago),
                observaciones=self.observaciones or None,
                items=[item],
            )
            with Session(engine) as session:
                result = OrderService(session).create_public_order(payload)
            extra = f" WhatsApp: {result.whatsapp_url}" if result.whatsapp_url else ""
            self.message = f"Pedido {result.pedido.codigo} creado. Total: {result.pedido.monto_total}.{extra}"
        except Exception as exc:
            self.message = str(exc)


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
        if not auth.is_authenticated:
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
        if not auth.is_authenticated:
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
        if not auth.is_admin:
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
        if not auth.is_admin:
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
        if not auth.is_admin:
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
