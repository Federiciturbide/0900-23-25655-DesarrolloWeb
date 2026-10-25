"""Punto de composición: selecciona adaptadores para ejecutar la aplicación."""

from application.ports import PersistencePort, QrEncoderPort
from infrastructure.adapters import LocalQrEncoderAdapter, SQLitePersistenceAdapter

persistence_port: PersistencePort = SQLitePersistenceAdapter()
qr_encoder_port: QrEncoderPort = LocalQrEncoderAdapter()
