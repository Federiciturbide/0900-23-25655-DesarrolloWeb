PRAGMA foreign_keys = ON;

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
