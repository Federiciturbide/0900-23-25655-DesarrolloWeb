"""Esquema SQLite, migración desde la primera entrega y datos iniciales."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp(value: datetime | None = None) -> str:
    return (value or now_utc()).isoformat()


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=15, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def password_digest(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    import hmac
    try:
        algorithm, salt_hex, expected_hex = stored.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
  nit TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '', loyalty_points INTEGER NOT NULL DEFAULT 0 CHECK(loyalty_points >= 0),
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers (
  id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE, business_name TEXT NOT NULL,
  contact_name TEXT NOT NULL DEFAULT '', nit TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
  category TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', stock REAL NOT NULL DEFAULT 0 CHECK(stock >= 0),
  supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS product_prices (
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  cost REAL NOT NULL CHECK(cost >= 0), sale_price REAL NOT NULL CHECK(sale_price >= 0),
  effective_from TEXT NOT NULL, effective_to TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_current_price ON product_prices(product_id) WHERE effective_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_prices_product_date ON product_prices(product_id,effective_from DESC,id DESC);
CREATE TABLE IF NOT EXISTS promotions (
  id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('discount','free_product','gift_voucher','half_second','wholesale','points')),
  category TEXT NOT NULL DEFAULT '', product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
  min_qty REAL NOT NULL DEFAULT 1 CHECK(min_qty > 0), discount_percent REAL NOT NULL DEFAULT 0 CHECK(discount_percent BETWEEN 0 AND 100),
  wholesale_price REAL NOT NULL DEFAULT 0 CHECK(wholesale_price >= 0), reward_product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
  voucher_amount REAL NOT NULL DEFAULT 0 CHECK(voucher_amount >= 0), points_per_unit INTEGER NOT NULL DEFAULT 0 CHECK(points_per_unit >= 0),
  starts_at TEXT, ends_at TEXT, active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0,1)), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promotions_active ON promotions(active,type);
CREATE TABLE IF NOT EXISTS cash_registers (
  id INTEGER PRIMARY KEY, opened_by INTEGER NOT NULL REFERENCES users(id), opened_at TEXT NOT NULL,
  opening_amount REAL NOT NULL CHECK(opening_amount >= 0), status TEXT NOT NULL CHECK(status IN ('OPEN','CLOSED')),
  closed_by INTEGER REFERENCES users(id), closed_at TEXT, counted_amount REAL, expected_cash REAL, difference REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_cash_register ON cash_registers(status) WHERE status='OPEN';
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY, number TEXT NOT NULL UNIQUE, register_id INTEGER NOT NULL REFERENCES cash_registers(id),
  client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
  customer_name TEXT NOT NULL, customer_nit TEXT NOT NULL DEFAULT '', customer_address TEXT NOT NULL DEFAULT '',
  subtotal REAL NOT NULL, line_discount REAL NOT NULL DEFAULT 0, voucher_discount REAL NOT NULL DEFAULT 0,
  points_discount REAL NOT NULL DEFAULT 0, discount_total REAL NOT NULL DEFAULT 0, total REAL NOT NULL,
  payment_method TEXT NOT NULL CHECK(payment_method IN ('Efectivo','Tarjeta de crédito','Tarjeta de débito')),
  amount_received REAL NOT NULL DEFAULT 0, change_due REAL NOT NULL DEFAULT 0, points_earned INTEGER NOT NULL DEFAULT 0,
  points_redeemed INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'COMPLETADA' CHECK(status IN ('COMPLETADA','ANULADA')),
  created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(created_at);
CREATE TABLE IF NOT EXISTS sale_lines (
  id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  product_id INTEGER REFERENCES products(id) ON DELETE SET NULL, sku TEXT NOT NULL, product_name TEXT NOT NULL,
  category TEXT NOT NULL, quantity REAL NOT NULL CHECK(quantity > 0), unit_price REAL NOT NULL,
  line_subtotal REAL NOT NULL, discount_amount REAL NOT NULL DEFAULT 0, line_total REAL NOT NULL,
  is_free INTEGER NOT NULL DEFAULT 0 CHECK(is_free IN (0,1)), promotion_id INTEGER REFERENCES promotions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_sale_lines_sale ON sale_lines(sale_id);
CREATE TABLE IF NOT EXISTS invoices (
  id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL UNIQUE REFERENCES sales(id) ON DELETE CASCADE,
  number TEXT NOT NULL UNIQUE, issued_at TEXT NOT NULL, qr_payload TEXT NOT NULL, promotion_text TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vouchers (
  id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, issued_sale_id INTEGER NOT NULL REFERENCES sales(id),
  redeemed_sale_id INTEGER REFERENCES sales(id), client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
  amount REAL NOT NULL CHECK(amount > 0), status TEXT NOT NULL DEFAULT 'DISPONIBLE' CHECK(status IN ('DISPONIBLE','USADO')),
  created_at TEXT NOT NULL, redeemed_at TEXT
);
CREATE TABLE IF NOT EXISTS loyalty_transactions (
  id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id), sale_id INTEGER REFERENCES sales(id),
  points_delta INTEGER NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS returns (
  id INTEGER PRIMARY KEY, number TEXT NOT NULL UNIQUE, sale_id INTEGER NOT NULL REFERENCES sales(id),
  sale_line_id INTEGER NOT NULL REFERENCES sale_lines(id), product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
  product_name TEXT NOT NULL, sku TEXT NOT NULL, quantity REAL NOT NULL CHECK(quantity > 0),
  reason TEXT NOT NULL CHECK(reason IN ('Daño','Vencimiento')), refund_amount REAL NOT NULL,
  payment_method TEXT NOT NULL CHECK(payment_method IN ('Efectivo','Tarjeta de crédito','Tarjeta de débito')),
  register_id INTEGER NOT NULL REFERENCES cash_registers(id), processed_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_returns_date ON returns(created_at);
CREATE TABLE IF NOT EXISTS purchases (
  id INTEGER PRIMARY KEY, number TEXT NOT NULL UNIQUE, supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  total REAL NOT NULL, created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_lines (
  id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
  product_id INTEGER REFERENCES products(id) ON DELETE SET NULL, sku TEXT NOT NULL, product_name TEXT NOT NULL,
  quantity REAL NOT NULL CHECK(quantity > 0), unit_cost REAL NOT NULL CHECK(unit_cost >= 0), line_total REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(created_at);
CREATE TABLE IF NOT EXISTS catalog_audit (
  id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  event TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER, details TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
"""


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(clients)")}
        if "loyalty_points" not in columns:
            connection.execute("ALTER TABLE clients ADD COLUMN loyalty_points INTEGER NOT NULL DEFAULT 0")
        now = stamp()
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            initial_password = os.environ.get("RINCON_ADMIN_PASSWORD")
            if not initial_password:
                initial_password = secrets.token_urlsafe(18)
                credential_file = path.parent / "credenciales_iniciales.txt"
                credential_file.write_text(
                    "Usuario: admin\nContraseña inicial: " + initial_password + "\n"
                    "Configura RINCON_ADMIN_PASSWORD para definirla manualmente.\n",
                    encoding="utf-8",
                )
            connection.execute(
                "INSERT INTO users(username,display_name,password_hash,created_at) VALUES (?,?,?,?)",
                ("admin", "Administración", password_digest(initial_password), now),
            )
        if connection.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO clients(code,name,nit,phone,email,address,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                [("CLI-001","Cliente de ejemplo 1","","","","",now,now),
                 ("CLI-002","Cliente de ejemplo 2","","","","",now,now),
                 ("CLI-003","Cliente de ejemplo 3","","","","",now,now)],
            )
        if connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO suppliers(code,business_name,contact_name,nit,phone,email,address,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                [("PRO-001","Proveedor de ejemplo 1","","","","","",now,now),
                 ("PRO-002","Proveedor de ejemplo 2","","","","","",now,now),
                 ("PRO-003","Proveedor de ejemplo 3","","","","","",now,now)],
            )
        if connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            suppliers = {row["code"]: row["id"] for row in connection.execute("SELECT id,code FROM suppliers")}
            sample_products = [
                ("SKU-001","Espagueti clásico 200 g","Pastas","Pasta de trigo",24,"PRO-001",4.25,6.00),
                ("SKU-002","Pollo fresco por libra","Cárnicos","Producto refrigerado",18,"PRO-003",11.50,15.00),
                ("SKU-003","Queso fresco 1 lb","Lácteos","Producto refrigerado",12,"PRO-002",18.00,23.00),
                ("SKU-004","Chocolate con leche 45 g","Golosinas","Barra individual",36,"PRO-001",2.75,4.00),
                ("SKU-005","Agua gaseosa 600 ml","Aguas gaseosas","Bebida individual",30,"PRO-001",3.50,5.00),
            ]
            for sku,name,category,description,stock,supplier,cost,price in sample_products:
                product_id = connection.execute(
                    "INSERT INTO products(sku,name,category,description,stock,supplier_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (sku,name,category,description,stock,suppliers[supplier],now,now),
                ).lastrowid
                connection.execute("INSERT INTO product_prices(product_id,cost,sale_price,effective_from) VALUES (?,?,?,?)",(product_id,cost,price,now))
        # Completa las siete familias indicadas en el proyecto sin duplicar
        # productos que la persona administradora ya haya cargado.
        suppliers = {row["code"]: row["id"] for row in connection.execute("SELECT id,code FROM suppliers")}
        existing_categories = {
            row["category"].strip().casefold()
            for row in connection.execute("SELECT DISTINCT category FROM products")
        }
        family_examples = [
            ("SKU-006","Longaniza familiar por libra","Embutidos","Embutido fresco",15,"PRO-003",15.00,20.00),
            ("SKU-007","Bebida deportiva 500 ml","Carbonatados","Bebida rehidratante",20,"PRO-001",5.00,8.00),
        ]
        for sku,name,category,description,stock,supplier,cost,price in family_examples:
            if category.casefold() in existing_categories:
                continue
            candidate = sku
            suffix = 2
            while connection.execute("SELECT 1 FROM products WHERE sku=? COLLATE NOCASE",(candidate,)).fetchone():
                candidate = f"{sku}-{suffix}"
                suffix += 1
            product_id = connection.execute(
                "INSERT INTO products(sku,name,category,description,stock,supplier_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (candidate,name,category,description,stock,suppliers.get(supplier),now,now),
            ).lastrowid
            connection.execute("INSERT INTO product_prices(product_id,cost,sale_price,effective_from) VALUES (?,?,?,?)",(product_id,cost,price,now))
            existing_categories.add(category.casefold())
        if connection.execute("SELECT COUNT(*) FROM promotions").fetchone()[0] == 0:
            products = {row["sku"]: row["id"] for row in connection.execute("SELECT id,sku FROM products")}
            samples = [
                ("DULCE10","10% en golosinas","discount","Golosinas",None,1,10,0,None,0,0,1),
                ("MITAD2","Segundo producto a mitad","half_second","Pastas",None,2,0,0,None,0,0,1),
                ("MAYOREO3","Precio de mayoreo desde 3","wholesale","Aguas gaseosas",None,3,0,4.25,None,0,0,1),
                ("PUNTOS2","Puntos por cárnicos","points","Cárnicos",None,1,0,0,None,0,2,1),
                ("REGALO","Producto gratuito al comprar 2 lácteos","free_product","Lácteos",None,2,0,0,products.get("SKU-004"),0,0,0),
                ("VALE15","Vale de regalo Q15","gift_voucher","Pastas",None,5,0,0,None,15,0,0),
            ]
            connection.executemany(
                "INSERT INTO promotions(code,name,type,category,product_id,min_qty,discount_percent,wholesale_price,reward_product_id,voucher_amount,points_per_unit,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [row + (now,now) for row in samples],
            )





