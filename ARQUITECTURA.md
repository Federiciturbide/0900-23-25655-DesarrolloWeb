# Arquitectura de La casa del rincón guatemalteco

## Plataforma y núcleo del negocio

La solución se ejecuta localmente en un navegador y usa tecnologías gratuitas: HTML, CSS, JavaScript, Python estándar y SQLite. El núcleo del negocio es la venta minorista de productos de consumo masivo con control de existencias, cobro, caja y promoción por familia.

## Modelo de tres capas

| Capa | Implementación | Responsabilidad |
|---|---|---|
| Presentación | public/index.html, public/styles.css, public/app.js | Menú superior, formularios, catálogos, punto de venta, facturas y reportes. Envía y recibe JSON por HTTP. |
| Aplicación | server.py, application/dependencies.py | Controladores HTTP, autenticación y coordinación de casos de uso: venta, devolución, compra, caja y reportes. |
| Dominio e infraestructura | domain/promotions.py, application/ports.py, infrastructure/adapters.py, database.py, qr.py | Políticas comerciales, contratos de salida, adaptadores concretos, esquema y almacenamiento relacional, y generación QR. |

El servidor escucha por defecto en 127.0.0.1:8000. La base de datos se guarda en data/rincon.sqlite3. No se conecta a servicios comerciales externos.

## Diseño guiado por el dominio (DDD)

### Lenguaje común

- Producto: artículo vendible con SKU, familia, existencia y precio vigente.
- Familia: grupo comercial del producto, como Pastas, Cárnicos, Embutidos, Lácteos, Golosinas, Aguas gaseosas o Carbonatados.
- Venta: operación de punto de venta con cliente, líneas, descuentos, pago y total.
- Caja: sesión abierta con fondo inicial, cobros en efectivo y cierre contado.
- Devolución: retorno por daño o vencimiento ligado a una línea facturada.
- Promoción: regla activa por producto o familia para descuento, regalo, vale, mayoreo, mitad de precio o puntos.

### Contextos delimitados

- Ventas (núcleo): despacho, precio, promociones, lealtad, cobro y factura QR.
- Catálogo y contactos: productos, precios, clientes y proveedores.
- Inventario: compras recibidas, existencias y devoluciones no vendibles por daño/vencimiento.
- Caja: apertura, movimientos de efectivo, esperado, contado y diferencia.
- Identidad: usuarios y sesiones con credenciales persistidas.
- Informes: lectura agregada de ventas, cierres, devoluciones, clientes y compras.

### Agregados e invariantes

- Producto: SKU único, existencia no negativa e historial de precios sin más de un precio vigente.
- Venta: líneas y factura asociada; el total no puede quedar negativo y la venta reduce existencias.
- Caja: una sesión abierta a la vez; requiere fondo inicial y conserva el cálculo del cierre.
- Devolución: corresponde a una línea de una venta completada y no excede las unidades restantes; por daño/vencimiento no incrementa el stock vendible.
- Compra: líneas asociadas al proveedor; al registrarla incrementa las existencias.
- Puntos y vales: movimientos vinculados a cliente y venta; un vale disponible se consume en una sola operación.

Las políticas de aplicación de descuentos, mayoreo, puntos y umbrales de promoción están implementadas como funciones puras en domain/promotions.py. La escritura transaccional y las validaciones de datos ocurren en el caso de venta.

## Arquitectura hexagonal

### Puerto de entrada

El navegador invoca rutas JSON. AppHandler en server.py traduce GET, POST, PUT y DELETE a operaciones de la aplicación.

### Puertos de salida

- PersistencePort: conexión e inicialización relacional requeridas por la aplicación.
- QrEncoderPort: generación de la matriz QR requerida por la facturación.

### Adaptadores

- SQLitePersistenceAdapter delega en database.py y el controlador sqlite3; su archivo es data/rincon.sqlite3.
- LocalQrEncoderAdapter delega en qr.py, que genera QR sin paquetes externos.
- La selección de adaptadores está en application/dependencies.py; para incorporar otra base o generador se puede sustituir el adaptador que implementa el mismo protocolo.

Las interfaces de puerto están definidas como Protocol de Python. Los casos de uso transaccionales permanecen en server.py para mantener la entrega compacta, mientras el cálculo de promociones está separado del transporte y de SQLite. PersistencePort abstrae la conexión, pero las consultas SQL todavía están en server.py; sustituir SQLite requeriría adaptar esas consultas. QrEncoderPort sí aísla el generador detrás de su contrato.

## Modelo C4 y Kanban

El archivo evidencias/modelo_c4.drawio contiene tres vistas editables: contexto, contenedores y componentes. evidencias/modelo_ddd.drawio muestra los contextos y sus relaciones. evidencias/arquitectura_hexagonal.drawio representa el flujo entre adaptadores, puertos y núcleo. evidencias/tablero_kanban.drawio documenta el flujo de trabajo y estado de entrega.
