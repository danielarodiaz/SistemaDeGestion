from __future__ import annotations

import argparse
import getpass
import os

from sqlmodel import Session

from gastroflow.data.database import engine
from gastroflow.domain.errors import DomainError
from gastroflow.services import AuthService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crea el primer usuario Admin de GastroFlow.")
    parser.add_argument("--username", default=os.getenv("FIRST_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("FIRST_ADMIN_PASSWORD"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    username = args.username or input("Username Admin: ").strip()
    password = args.password or getpass.getpass("Password Admin: ")

    try:
        with Session(engine) as session:
            admin = AuthService(session).create_first_admin(username=username, password=password)
    except DomainError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Admin creado: {admin.username}")


if __name__ == "__main__":
    main()
