# La casa del rincón guatemalteco

Aplicación web local para ventas e inventario de un negocio de productos de consumo masivo.

Incluye acceso de usuario, catálogos, precios con historial, punto de venta, promociones, caja, facturación con QR, devoluciones, compras, reportes y modelos C4, DDD, hexagonal y Kanban en Draw.io.

## Inicio rápido

1. Instala Python 3.10 o superior en Windows.
2. Ejecuta iniciar.bat.
3. Abre http://127.0.0.1:8000.
4. En una base nueva, consulta la contraseña inicial en data/credenciales_iniciales.txt o define RINCON_ADMIN_PASSWORD antes del primer inicio.

La base SQLite se crea localmente al iniciar la aplicación. El archivo de datos operativo no se versiona; el esquema y las semillas están en database.py y ESQUEMA_BD.sql. Cambia la contraseña de demostración antes de usar datos reales.

## Arquitectura

- Tres capas: interfaz web, aplicación HTTP y dominio/infraestructura.
- DDD: contextos de ventas, catálogo, inventario, caja, identidad e informes.
- Hexagonal: puertos de persistencia y QR con adaptadores locales.
- Kanban: tablero editable dentro de evidencias.
- C4: contexto, contenedores y componentes en tres páginas Draw.io.

Consulta INSTRUCCIONES.md y ARQUITECTURA.md para detalles.


