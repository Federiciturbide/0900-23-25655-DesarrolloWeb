"""Adaptadores concretos de los puertos de aplicación."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import database
import qr


class SQLitePersistenceAdapter:
    """Adapta SQLite y database.py al puerto de persistencia."""

    def connect(self, path: Path) -> sqlite3.Connection:
        return database.connect(path)

    def initialize_database(self, path: Path) -> None:
        database.initialize_database(path)


class LocalQrEncoderAdapter:
    """Adapta el generador QR puro de Python al puerto de salida."""

    def encode(self, value: str) -> list[list[bool]]:
        return qr.encode(value)
