from sqlmodel import Session
from sqlalchemy import text


def next_business_code(session: Session, sequence_name: str, prefix: str) -> str:
    next_value = session.exec(text(f"SELECT nextval('{sequence_name}')")).one()[0]
    return f"{prefix}-{int(next_value):04d}"
