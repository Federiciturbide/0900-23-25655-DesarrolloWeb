"""Puertos requeridos por la aplicación para persistencia y generación QR."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol


class PersistencePort(Protocol):
    def connect(self, path: Path) -> sqlite3.Connection: ...

    def initialize_database(self, path: Path) -> None: ...


class QrEncoderPort(Protocol):
    def encode(self, value: str) -> list[list[bool]]: ...
