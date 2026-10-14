"""Explicit local provisioning utility; never run during application startup."""

import argparse
from getpass import getpass

import psycopg
from psycopg import sql
from pydantic import ValidationError
from pydantic_settings import SettingsError

from app.core.config import Settings, load_settings


def provision_database(settings: Settings, admin_user: str, admin_password: str) -> None:
    with psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname="postgres",
        user=admin_user,
        password=admin_password,
        sslmode=settings.db_sslmode,
        connect_timeout=settings.db_connect_timeout,
        options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
        autocommit=True,
    ) as connection:
        role = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (settings.db_user,)
        ).fetchone()
        if role is None:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
                ).format(
                    sql.Identifier(settings.db_user),
                    sql.Literal(settings.db_password.get_secret_value()),
                )
            )
        database = connection.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
            (settings.db_name,),
        ).fetchone()
        if database is None:
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(settings.db_name), sql.Identifier(settings.db_user)
                )
            )
        elif database[0] != settings.db_user:
            raise RuntimeError("Existing database has a different owner; no ownership was changed.")
        # Existing roles/passwords/databases are never altered or deleted.


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the configured local PostgreSQL role/database"
    )
    parser.add_argument("--admin-user", required=True)
    args = parser.parse_args()
    try:
        settings = load_settings()
        provision_database(settings, args.admin_user, getpass("PostgreSQL admin password: "))
    except (ValidationError, SettingsError, psycopg.Error, RuntimeError):
        print(
            "Database setup failed. Check configuration and admin access; details were not logged."
        )
        return 1
    print(
        "Database and role are present. Existing passwords were preserved. Run app.db.check next."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
