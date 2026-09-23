from datetime import datetime, timezone

import pytest

from gastroflow.domain.enums import RolUsuario
from gastroflow.domain.errors import AuthorizationError, ValidationError
from gastroflow.models import UsuarioRead
from gastroflow.security.passwords import hash_password, verify_password
from gastroflow.services import AuthService


def test_hash_password_does_not_store_plain_text() -> None:
    password_hash = hash_password("super-secret")

    assert password_hash != "super-secret"
    assert verify_password("super-secret", password_hash)
    assert not verify_password("wrong-secret", password_hash)


def test_hash_password_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        hash_password("short")


def test_require_admin_rejects_owner() -> None:
    user = UsuarioRead(
        id=1,
        username="dueno",
        rol=RolUsuario.DUENO,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with pytest.raises(AuthorizationError):
        AuthService(session=None).require_admin(user)  # type: ignore[arg-type]


def test_require_owner_or_admin_accepts_owner() -> None:
    user = UsuarioRead(
        id=1,
        username="dueno",
        rol=RolUsuario.DUENO,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    AuthService(session=None).require_owner_or_admin(user)  # type: ignore[arg-type]
