# Matriz de requisitos y evidencias

El listado de la imagen adjunta se interpreta como especificación del sistema. Los puntos siguientes describen lo implementado en la aplicación.

| Punto | Función implementada | Dónde consultarlo | Registro relacionado |
|---|---|---|---|
| 1 | Inicio y cierre de sesión con validación en SQLite | Pantalla de ingreso | users, sessions |
| 2 | Clientes, proveedores, productos, costo y precio de venta | Contactos y Almacén | clients, suppliers, products, product_prices |
| 3 | Despacho por SKU, cantidad, subtotales, descuento y total | Punto de Venta | sales, sale_lines |
| 4 | Devolución por daño o vencimiento; saldo de unidades retornables y monto reembolsado | Ventas > Devoluciones | returns |
| 5 | Pago en efectivo, tarjeta de crédito o débito; cálculo de cambio en efectivo | Punto de Venta | sales.payment_method, amount_received, change_due |
| 6 | Factura con datos del cliente, productos, cantidades, precio, descuentos, total y QR imprimible | Ventas > Facturación; después de cobrar | invoices, sales, sale_lines |
| 7 | Ventas/ingresos, corte de caja, devoluciones, resumen por cliente y compra para existencias | Informes | sales, cash_registers, returns, clients, purchases, purchase_lines |
| 8 | QR de factura que permite consultar promoción y tipo registrados | Factura > QR; Configuración > Lectura de código QR | invoices.qr_payload, invoices.promotion_text |
| 9 | Menú superior y navegación lateral para abrir módulos | Encabezado y menú lateral | Navegación web |
| 10 | Apertura/cierre de caja y control del fondo, ventas, efectivo contado y diferencia | Punto de Venta > Caja | cash_registers |
| 10a | Descuento de producto, producto gratuito, vale, segundo artículo a mitad, mayoreo por familia y puntos canjeables | Configuración > Promociones | promotions, vouchers, loyalty_transactions |

## Recorrido sugerido para una demostración

1. Abre iniciar.bat e ingresa como admin con la clave inicial indicada en INSTRUCCIONES.md.
2. Abre Caja y registra un fondo de apertura.
3. En Promociones revisa las reglas de muestra o activa una regla adicional.
4. En Punto de Venta agrega un producto, asigna cliente si corresponde, selecciona medio de pago y cobra.
5. La aplicación guarda venta y factura, descuenta existencias, registra puntos/promoción y muestra la factura con QR.
6. Lee el QR desde Lectura de código QR para ver la promoción asociada.
7. Registra una devolución desde la factura o ingresa una compra a proveedor para aumentar existencias.
8. En Informes consulta el rango de fechas y revisa ingresos, devoluciones, clientes, compras y cortes.

## Reglas de operación

- Se necesita una caja abierta para cobrar ventas y procesar devoluciones.
- Una devolución no puede exceder la cantidad facturada menos devoluciones previas de esa línea.
- Los artículos devueltos por daño o vencimiento no se agregan otra vez al inventario.
- Una promoción debe estar activa, vigente y tener definido producto o familia.
- La cantidad de mayoreo se acumula por familia; los puntos se registran por unidad.
- La redención implementada usa Q1 por punto como regla demostrativa ajustable según las políticas del negocio.
- Las compras a proveedor incrementan existencias y dejan historial del costo.

## Criterios de arquitectura del documento

- Desarrollo gratuito/local: navegador web, Python estándar y SQLite; no requiere licencias ni dependencias de terceros.
- Tres capas: presentación en public, aplicación HTTP/casos de uso en server.py y dominio/infraestructura/persistencia en sus módulos.
- Núcleo de consumo masivo: venta por familia de producto, control de existencia, precio, promoción y cobro.
- DDD: contextos de Ventas, Catálogo y contactos, Inventario, Caja, Identidad e Informes.
- Hexagonal: puertos PersistencePort y QrEncoderPort, con adaptadores SQLite y QR local.
- Kanban: tablero visual en tablero_kanban.drawio con WIP de dos tarjetas para Desarrollo y Revisión.
- C4: tres vistas editables (contexto, contenedores y componentes) en modelo_c4.drawio.
