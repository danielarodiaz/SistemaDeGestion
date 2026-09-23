from decimal import Decimal

import pytest

from gastroflow.domain.enums import EstadoPedido, ReglaPrecioCombo
from gastroflow.domain.errors import ValidationError
from gastroflow.domain.order_state import assert_valid_order_transition
from gastroflow.models import ComboRegla
from gastroflow.services.orders import OrderService, normalize_phone


def test_order_transition_allows_expected_path() -> None:
    assert_valid_order_transition(EstadoPedido.PEDIDO, EstadoPedido.EN_PROCESO)
    assert_valid_order_transition(EstadoPedido.EN_PROCESO, EstadoPedido.ENTREGADO)


def test_order_transition_rejects_terminal_regression() -> None:
    with pytest.raises(ValidationError):
        assert_valid_order_transition(EstadoPedido.ENTREGADO, EstadoPedido.EN_PROCESO)


def test_combo_price_uses_average_rule() -> None:
    combo = ComboRegla(
        producto_a_id=1,
        producto_b_id=2,
        requiere_confirmacion=False,
        regla_precio=ReglaPrecioCombo.PROMEDIO,
    )

    price = OrderService(session=None)._combo_price(  # type: ignore[arg-type]
        combo,
        Decimal("5500.00"),
        Decimal("7000.00"),
    )

    assert price == Decimal("6250.00")


def test_normalize_phone_keeps_plus_and_digits() -> None:
    assert normalize_phone(" +54 381 555-1234 ") == "+543815551234"
    assert normalize_phone("0054 381 555-1234") == "+543815551234"
