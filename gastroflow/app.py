from __future__ import annotations

import reflex as rx

from gastroflow.states.app_state import (
    AdminCrudState,
    AuthState,
    ExpenseState,
    OperationsState,
    PublicOrderState,
)


def shell(*children: rx.Component) -> rx.Component:
    return rx.box(
        rx.vstack(
            nav(),
            rx.box(*children, width="100%", max_width="1120px", padding="1rem"),
            spacing="4",
            align="center",
            width="100%",
        ),
        min_height="100vh",
        background="#f7f7f4",
        color="#20201d",
    )


def nav() -> rx.Component:
    link_style = {
        "padding": "0.65rem 0.8rem",
        "border_radius": "8px",
        "background": "#ffffff",
        "border": "1px solid #deded6",
        "font_weight": "600",
    }
    return rx.hstack(
        rx.heading("GastroFlow", size="6"),
        rx.spacer(),
        rx.link("Pedido", href="/", style=link_style),
        rx.link("Login", href="/login", style=link_style),
        rx.link("Operaciones", href="/operaciones", style=link_style),
        rx.link("Gastos", href="/gastos", style=link_style),
        rx.link("Admin", href="/admin", style=link_style),
        width="100%",
        max_width="1120px",
        padding="1rem",
        wrap="wrap",
        align="center",
    )


def field(label: str, control: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.text(label, font_weight="600", font_size="0.9rem"),
        control,
        spacing="1",
        align="stretch",
        width="100%",
    )


def panel(*children: rx.Component) -> rx.Component:
    return rx.box(
        rx.vstack(*children, spacing="4", align="stretch"),
        width="100%",
        background="#ffffff",
        border="1px solid #deded6",
        border_radius="8px",
        padding="1rem",
    )


def product_card(product: rx.Var[dict]) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(product["nombre"], font_weight="700"),
            rx.text("$", product["precio"]),
            rx.text("ID ", product["id"], font_size="0.8rem", color="#666"),
            rx.button("Elegir", on_click=PublicOrderState.select_product(product["id"]), width="100%"),
            spacing="2",
            align="stretch",
        ),
        border="1px solid #deded6",
        border_radius="8px",
        padding="0.9rem",
        background="#fbfbf8",
    )


def zone_card(zone: rx.Var[dict]) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(zone["nombre"], font_weight="700"),
            rx.text("$", zone["costo"]),
            rx.text("ID ", zone["id"], font_size="0.8rem", color="#666"),
            spacing="1",
            align="stretch",
        ),
        border="1px solid #deded6",
        border_radius="8px",
        padding="0.75rem",
        background="#fbfbf8",
    )


def public_page() -> rx.Component:
    return shell(
        rx.vstack(
            rx.heading("Nuevo pedido", size="7"),
            rx.text("Formulario publico para clientes"),
            panel(
                field(
                    "Cliente",
                    rx.input(
                        value=PublicOrderState.nombre_apellido,
                        on_change=PublicOrderState.set_nombre_apellido,
                        placeholder="Nombre y apellido",
                        size="3",
                    ),
                ),
                field(
                    "Telefono",
                    rx.input(
                        value=PublicOrderState.telefono,
                        on_change=PublicOrderState.set_telefono,
                        placeholder="+54 381 ...",
                        size="3",
                    ),
                ),
                field(
                    "Fecha de entrega",
                    rx.input(
                        value=PublicOrderState.fecha_entrega,
                        on_change=PublicOrderState.set_fecha_entrega,
                        placeholder="AAAA-MM-DD",
                        size="3",
                    ),
                ),
                rx.heading("Producto", size="5"),
                rx.grid(
                    rx.foreach(PublicOrderState.products, product_card),
                    columns="repeat(auto-fit, minmax(180px, 1fr))",
                    spacing="3",
                    width="100%",
                ),
                field(
                    "Cantidad",
                    rx.input(
                        value=PublicOrderState.quantity,
                        on_change=PublicOrderState.set_quantity,
                        type="number",
                        min="1",
                        size="3",
                    ),
                ),
                field(
                    "Segundo sabor opcional",
                    rx.input(
                        value=PublicOrderState.selected_combo_id,
                        on_change=PublicOrderState.set_selected_combo_id,
                        placeholder="ID de producto combo, opcional",
                        size="3",
                    ),
                ),
                field(
                    "Direccion",
                    rx.input(
                        value=PublicOrderState.direccion_delivery,
                        on_change=PublicOrderState.set_direccion_delivery,
                        size="3",
                    ),
                ),
                field(
                    "Zona de envio",
                    rx.input(
                        value=PublicOrderState.zona_envio_id,
                        on_change=PublicOrderState.set_zona_envio_id,
                        placeholder="ID de zona, vacio para retiro",
                        size="3",
                    ),
                ),
                rx.grid(
                    rx.foreach(PublicOrderState.zones, zone_card),
                    columns="repeat(auto-fit, minmax(180px, 1fr))",
                    spacing="3",
                    width="100%",
                ),
                field(
                    "Forma de pago",
                    rx.hstack(
                        rx.button(
                            "Efectivo",
                            on_click=PublicOrderState.set_forma_pago("efectivo"),
                            size="3",
                        ),
                        rx.button(
                            "Transferencia",
                            on_click=PublicOrderState.set_forma_pago("transferencia"),
                            size="3",
                        ),
                    ),
                ),
                field(
                    "Observaciones",
                    rx.text_area(
                        value=PublicOrderState.observaciones,
                        on_change=PublicOrderState.set_observaciones,
                    ),
                ),
                rx.button("Confirmar pedido", on_click=PublicOrderState.submit_order, size="4"),
                rx.text(PublicOrderState.message, color="#2f5d50", font_weight="600"),
            ),
            spacing="4",
            align="stretch",
            width="100%",
        )
    )


def login_page() -> rx.Component:
    return shell(
        panel(
            rx.heading("Login operativo", size="7"),
            field("Usuario", rx.input(value=AuthState.username, on_change=AuthState.set_username, size="3")),
            field(
                "Password",
                rx.input(
                    value=AuthState.password,
                    on_change=AuthState.set_password,
                    type="password",
                    size="3",
                ),
            ),
            rx.hstack(
                rx.button("Ingresar", on_click=AuthState.login, size="3"),
                rx.button("Salir", on_click=AuthState.logout, size="3", variant="outline"),
            ),
            rx.text("Usuario actual: ", AuthState.username, " / ", AuthState.role),
            rx.text(AuthState.message, color="#2f5d50", font_weight="600"),
        )
    )


def order_card(order: rx.Var[dict]) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(rx.text(order["codigo"], font_weight="800"), rx.spacer(), rx.text(order["estado"])),
            rx.text(order["cliente"]),
            rx.text("Total $", order["total"]),
            rx.text(order["fecha"], color="#666"),
            rx.hstack(
                rx.button("En proceso", on_click=OperationsState.transition(order["id"], "en_proceso")),
                rx.button("Entregado", on_click=OperationsState.transition(order["id"], "entregado")),
                rx.button("Cancelar", on_click=OperationsState.transition(order["id"], "cancelado")),
                wrap="wrap",
            ),
            spacing="3",
            align="stretch",
        ),
        background="#ffffff",
        border="1px solid #deded6",
        border_radius="8px",
        padding="1rem",
    )


def operations_page() -> rx.Component:
    return shell(
        rx.vstack(
            rx.heading("Operaciones", size="7"),
            rx.button("Actualizar", on_click=OperationsState.load_orders),
            rx.text(OperationsState.message, color="#7a3d16", font_weight="600"),
            rx.grid(
                rx.foreach(OperationsState.orders, order_card),
                columns="repeat(auto-fit, minmax(240px, 1fr))",
                spacing="3",
                width="100%",
            ),
            spacing="4",
            align="stretch",
            width="100%",
        )
    )


def expense_card(expense: rx.Var[dict]) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(expense["codigo"], font_weight="800"),
            rx.text(expense["fecha"]),
            rx.text(expense["cantidad"], " ", expense["unidad"]),
            rx.text("$", expense["precio"]),
            rx.text(expense["lugar"], color="#666"),
            spacing="2",
            align="stretch",
        ),
        background="#ffffff",
        border="1px solid #deded6",
        border_radius="8px",
        padding="1rem",
    )


def expenses_page() -> rx.Component:
    return shell(
        rx.vstack(
            rx.heading("Gastos", size="7"),
            panel(
                field("Fecha", rx.input(value=ExpenseState.fecha, on_change=ExpenseState.set_fecha, placeholder="AAAA-MM-DD")),
                field("Motivo", rx.input(value=ExpenseState.motivo_nombre, on_change=ExpenseState.set_motivo_nombre)),
                field("Marca", rx.input(value=ExpenseState.marca_nombre, on_change=ExpenseState.set_marca_nombre)),
                field("Cantidad", rx.input(value=ExpenseState.cantidad, on_change=ExpenseState.set_cantidad)),
                field("Unidad", rx.input(value=ExpenseState.unidad_medida, on_change=ExpenseState.set_unidad_medida)),
                field("Precio", rx.input(value=ExpenseState.precio, on_change=ExpenseState.set_precio)),
                field("Lugar", rx.input(value=ExpenseState.lugar_texto, on_change=ExpenseState.set_lugar_texto)),
                rx.hstack(
                    rx.button("Guardar gasto", on_click=ExpenseState.submit_expense),
                    rx.button("Actualizar lista", on_click=ExpenseState.load_expenses, variant="outline"),
                ),
                rx.text(ExpenseState.message, color="#2f5d50", font_weight="600"),
            ),
            rx.grid(
                rx.foreach(ExpenseState.expenses, expense_card),
                columns="repeat(auto-fit, minmax(220px, 1fr))",
                spacing="3",
                width="100%",
            ),
            spacing="4",
            align="stretch",
            width="100%",
        )
    )


def table_button(table_name: rx.Var[str]) -> rx.Component:
    return rx.button(table_name, on_click=AdminCrudState.set_table(table_name), variant="outline")


def record_card(record: rx.Var[dict]) -> rx.Component:
    return rx.box(
        rx.text(record["display"]),
        background="#ffffff",
        border="1px solid #deded6",
        border_radius="8px",
        padding="0.75rem",
        overflow_x="auto",
        font_family="monospace",
        font_size="0.85rem",
    )


def admin_page() -> rx.Component:
    return shell(
        rx.vstack(
            rx.heading("Administracion", size="7"),
            panel(
                rx.text("Tabla", font_weight="700"),
                rx.hstack(rx.foreach(AdminCrudState.tables, table_button), wrap="wrap"),
                field(
                    "JSON de alta/edicion",
                    rx.text_area(
                        value=AdminCrudState.payload_json,
                        on_change=AdminCrudState.set_payload_json,
                        min_height="160px",
                    ),
                ),
                field("ID para editar/borrar", rx.input(value=AdminCrudState.selected_id, on_change=AdminCrudState.set_selected_id)),
                rx.hstack(
                    rx.button("Listar", on_click=AdminCrudState.load_records),
                    rx.button("Crear", on_click=AdminCrudState.create_record),
                    rx.button("Actualizar", on_click=AdminCrudState.update_record),
                    rx.button("Borrar", on_click=AdminCrudState.delete_record, color_scheme="red"),
                    wrap="wrap",
                ),
                rx.text("Tabla actual: ", AdminCrudState.table_name),
                rx.text(AdminCrudState.message, color="#7a3d16", font_weight="600"),
            ),
            rx.vstack(
                rx.foreach(AdminCrudState.records, record_card),
                spacing="2",
                align="stretch",
                width="100%",
            ),
            spacing="4",
            align="stretch",
            width="100%",
        )
    )


app = rx.App()
app.add_page(public_page, route="/", on_load=PublicOrderState.load_catalog)
app.add_page(login_page, route="/login")
app.add_page(operations_page, route="/operaciones", on_load=OperationsState.load_orders)
app.add_page(expenses_page, route="/gastos", on_load=ExpenseState.load_expenses)
app.add_page(admin_page, route="/admin")
