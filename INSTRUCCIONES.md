# La casa del rincón guatemalteco

Sistema local para controlar acceso, catálogos, existencias, ventas, cobros, devoluciones, compras, caja, facturación, promociones y reportes.

## Iniciar el sistema

1. En Windows, abre iniciar.bat.
2. Espera el mensaje que indica que el servidor está disponible.
3. En el navegador entra a http://127.0.0.1:8000.
4. Para detenerlo, vuelve a la ventana del servidor y presiona Ctrl+C.

Requiere Windows 10 u 11 y Python 3.10 o superior. No instala paquetes externos ni requiere conexión a internet.

## Cuenta inicial

- Usuario: admin
- En una base nueva, la contraseña se genera y guarda en `data/credenciales_iniciales.txt`.
- Puedes definir `RINCON_ADMIN_PASSWORD` antes del primer inicio para establecerla manualmente.

La contraseña se almacena como hash scrypt con sal aleatoria. Conserva la credencial fuera del repositorio.

## Funciones incluidas

1. Acceso de usuario: inicio y cierre de sesión con sesión persistente validada desde SQLite.
2. Catálogos: clientes, proveedores, productos, existencias y precios de costo/venta con historial.
3. Despacho y punto de venta: agrega productos por SKU, captura cantidades y calcula subtotales y total.
4. Devoluciones: registra productos dañados o vencidos, controla el saldo de unidades que aún pueden devolverse y calcula el reembolso.
5. Cobro: efectivo, tarjeta de crédito o tarjeta de débito; en efectivo calcula el cambio.
6. Facturación: guarda los datos del cliente, las líneas vendidas, descuentos, total, forma de pago y un código QR por factura. La factura se puede imprimir.
7. Reportes por periodo: ventas e ingresos por forma de pago, cierres de caja, devoluciones, resumen de clientes y compras para inventario.
8. Lectura QR: consulta la factura y la promoción asociada desde el texto del QR; permite usar lector/cámara cuando el navegador ofrece BarcodeDetector.
9. Menú interactivo: todos los módulos se abren desde el menú superior, sin menú lateral.
10. Caja y promociones: controla fondo de apertura, efectivo esperado, efectivo contado y diferencia al cierre. Admite descuento porcentual, producto gratuito, vale de regalo, segundo producto a mitad, mayoreo por familia y acumulación de puntos.

El catálogo admite las siete familias del proyecto: Pastas, Productos cárnicos, Embutidos, Lácteos, Golosinas, Aguas gaseosas y Carbonatados. Para una base nueva o una migración sin Embutidos/Carbonatados se agregan dos productos de muestra de esas familias; no se duplican categorías ya existentes.

Las promociones se mantienen desde Promociones en el menú superior. Para que se apliquen en caja deben estar activas, dentro de su periodo y configuradas por familia o producto. El precio por mayoreo se aplica al alcanzar la cantidad mínima acumulada dentro de la misma familia. Los puntos se acumulan por unidad según la regla activa; en esta versión un punto equivale a Q1 al redimirlos.

Las devoluciones por daño o vencimiento no reingresan al inventario. La devolución debe corresponder a una factura y requiere caja abierta. Las compras sí incrementan existencias y pueden guardar un costo actualizado sin borrar el historial de precios.

## Diseño de interfaz

La interfaz usa un estilo ERP tradicional inspirado en la referencia: barra superior naranja con todos los accesos, áreas de trabajo blancas, formularios y tablas compactos, bordes sencillos y botones rectangulares.

## Arquitectura del proyecto

- Tres capas: presentación web en public; aplicación HTTP y casos de uso en server.py; dominio, adaptadores y persistencia local en domain, application, infrastructure y database.py.
- DDD: los contextos de ventas (núcleo del negocio), inventario, caja, catálogo/contactos, identidad y reportes se describen en ARQUITECTURA.md y evidencias/modelo_ddd.drawio.
- Hexagonal: application/ports.py define los puertos de persistencia y generación QR; infrastructure/adapters.py adapta SQLite y el generador QR local. application/dependencies.py compone los adaptadores.
- Kanban: el tablero de entrega se conserva como evidencias/tablero_kanban.drawio.
- C4: contexto, contenedores y componentes en evidencias/modelo_c4.drawio.

El proyecto es local y de demostración; no depende de servicios externos ni requiere licencias o paquetes adicionales.

## Archivos

- server.py: servidor local y operaciones de aplicación.
- application/: puertos, casos de uso y selección de adaptadores.
- domain/: reglas del dominio para promociones y puntos.
- infrastructure/: adaptadores para SQLite y QR.
- database.py: esquema, migración y datos de demostración.
- qr.py: generación local de códigos QR sin librerías externas.
- public: pantallas, estilos y lógica del navegador.
- data/rincon.sqlite3: base relacional persistente.
- ESQUEMA_BD.sql: definición de tablas, llaves e índices.
- evidencias: diagramas C4, DDD y hexagonal, tablero Kanban, matriz de requisitos y estado de base.

## Respaldo de datos

Para conservar los datos, copia periódicamente la carpeta data y guarda el respaldo con el servidor detenido. No elimines data/rincon.sqlite3 si deseas conservar ventas, movimientos de inventario y facturas.

