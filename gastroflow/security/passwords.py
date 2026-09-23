import bcrypt

from gastroflow.domain.errors import ValidationError

MIN_PASSWORD_LENGTH = 8
MAX_BCRYPT_PASSWORD_BYTES = 72


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError("La password debe tener al menos 8 caracteres.")
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValidationError("La password no puede superar 72 bytes para bcrypt.")


def hash_password(password: str) -> str:
    validate_password(password)
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
