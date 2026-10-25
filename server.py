"""Servidor local de tres capas para La casa del rincón guatemalteco."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
from datetime import timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import database
from application.dependencies import persistence_port, qr_encoder_port
from domain import promotions as promotion_rules

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
DB_PATH = ROOT / "data" / "rincon.sqlite3"
HOST = os.environ.get("RINCON_HOST", "127.0.0.1")
PORT = int(os.environ.get("RINCON_PORT", "8000"))
SESSION_HOURS = 12
PAYMENT_METHODS = {"Efectivo", "Tarjeta de crédito", "Tarjeta de débito"}


def now() -> str:
    return database.stamp()


def rounded(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def as_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def safe_rows(rows):
    return [dict(row) for row in rows]


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "RinconERP/2.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, payload, status: int = 200, headers: dict[str, str] | None = None) -> None:
        body = as_json(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; media-src 'self' blob:")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_error_response(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self.send_json({"error": message}, status)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                raise ValueError
            value = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (json.JSONDecodeError, ValueError):
            raise ValueError("El formato de la solicitud no es válido.")

    def cookie_value(self, key: str) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            return cookie[key].value if key in cookie else None
        except Exception:
            return None

    def current_user(self):
        token = self.cookie_value("rincon_session")
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        with persistence_port.connect(DB_PATH) as connection:
            return connection.execute(
                "SELECT u.id,u.username,u.display_name FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=? AND s.expires_at>? AND u.active=1", (token_hash, now())
            ).fetchone()

    def require_user(self):
        user = self.current_user()
        if user is None:
            self.send_json({"error": "Inicia sesión para continuar."}, HTTPStatus.UNAUTHORIZED)
        return user

    def audit(self, user_id: int, event: str, entity: str, entity_id: int | None = None, details: str = "") -> None:
        with persistence_port.connect(DB_PATH) as connection:
            connection.execute(
                "INSERT INTO catalog_audit(user_id,event,entity,entity_id,details,created_at) VALUES (?,?,?,?,?,?)",
                (user_id,event,entity,entity_id,details[:300],now()),
            )

    @staticmethod
    def need(payload: dict, key: str, label: str) -> str:
        value = str(payload.get(key, "")).strip()
        if not value:
            raise ValueError(f"El campo {label} es obligatorio.")
        return value

    @staticmethod
    def numeric(payload: dict, key: str, label: str, minimum: float = 0) -> float:
        try:
            value = float(payload.get(key, 0))
        except (TypeError, ValueError):
            raise ValueError(f"El campo {label} debe ser numérico.")
        if value < minimum:
            raise ValueError(f"El campo {label} debe ser al menos {minimum}.")
        return value

    @staticmethod
    def db_error(exc: Exception) -> str:
        message = str(exc)
        for key, label in (("clients.code","código de cliente"),("suppliers.code","código de proveedor"),
                           ("products.sku","SKU"),("promotions.code","código de promoción")):
            if key in message and "UNIQUE constraint failed" in message:
                return f"Ese {label} ya existe."
        if "UNIQUE constraint failed" in message:
            return "Ya existe un registro con esos datos."
        if "FOREIGN KEY constraint failed" in message:
            return "Selecciona un registro relacionado válido."
        return message if isinstance(exc, ValueError) else "No se pudo guardar. Revisa los datos e intenta de nuevo."

    @staticmethod
    def catalog_path(path: str):
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "clients"] and parts[2].isdigit():
            return "clients", int(parts[2])
        if len(parts) == 3 and parts[0:2] == ["api", "suppliers"] and parts[2].isdigit():
            return "suppliers", int(parts[2])
        if len(parts) == 3 and parts[0:2] == ["api", "products"] and parts[2].isdigit():
            return "products", int(parts[2])
        if len(parts) == 3 and parts[0:2] == ["api", "promotions"] and parts[2].isdigit():
            return "promotions", int(parts[2])
        return None, None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        if not path.startswith("/api/"):
            self.path = "/index.html" if path in ("", "/") else path
            if path == "/favicon.ico":
                self.send_response(204); self.end_headers(); return
            return super().do_GET()
        if path == "/api/session":
            user = self.current_user()
            return self.send_json({"authenticated": bool(user), "user": dict(user) if user else None})
        user = self.require_user()
        if not user:
            return
        try:
            if path == "/api/dashboard":
                with persistence_port.connect(DB_PATH) as connection:
                    register = self.register_summary(connection)
                    counts = {key: connection.execute(sql).fetchone()[0] for key,sql in {
                        "clients":"SELECT COUNT(*) FROM clients WHERE active=1",
                        "suppliers":"SELECT COUNT(*) FROM suppliers WHERE active=1",
                        "products":"SELECT COUNT(*) FROM products WHERE active=1",
                        "low_stock":"SELECT COUNT(*) FROM products WHERE active=1 AND stock<=5",
                        "today_sales":"SELECT COUNT(*) FROM sales WHERE date(created_at)=date('now','localtime') AND status='COMPLETADA'",
                        "today_total":"SELECT COALESCE(SUM(total),0) FROM sales WHERE date(created_at)=date('now','localtime') AND status='COMPLETADA'",
                        "today_returns":"SELECT COUNT(*) FROM returns WHERE date(created_at)=date('now','localtime')",
                    }.items()}
                return self.send_json({**counts,"cash_register":register})
            if path == "/api/clients":
                with persistence_port.connect(DB_PATH) as c:
                    return self.send_json(safe_rows(c.execute("SELECT * FROM clients ORDER BY active DESC,name COLLATE NOCASE").fetchall()))
            if path == "/api/suppliers":
                with persistence_port.connect(DB_PATH) as c:
                    return self.send_json(safe_rows(c.execute("SELECT * FROM suppliers ORDER BY active DESC,business_name COLLATE NOCASE").fetchall()))
            if path == "/api/products":
                with persistence_port.connect(DB_PATH) as c:
                    rows = c.execute("SELECT p.*,s.business_name supplier_name,pp.cost,pp.sale_price,pp.effective_from price_since "
                        "FROM products p LEFT JOIN suppliers s ON s.id=p.supplier_id "
                        "LEFT JOIN product_prices pp ON pp.product_id=p.id AND pp.effective_to IS NULL "
                        "ORDER BY p.active DESC,p.name COLLATE NOCASE").fetchall()
                    return self.send_json(safe_rows(rows))
            if path == "/api/suppliers/options":
                with persistence_port.connect(DB_PATH) as c:
                    return self.send_json(safe_rows(c.execute("SELECT id,business_name FROM suppliers WHERE active=1 ORDER BY business_name").fetchall()))
            if path == "/api/products/options":
                with persistence_port.connect(DB_PATH) as c:
                    return self.send_json(safe_rows(c.execute("SELECT p.id,p.sku,p.name,p.category,p.stock,pp.sale_price,pp.cost "
                        "FROM products p LEFT JOIN product_prices pp ON pp.product_id=p.id AND pp.effective_to IS NULL "
                        "WHERE p.active=1 ORDER BY p.name").fetchall()))
            if path == "/api/promotions":
                with persistence_port.connect(DB_PATH) as c:
                    return self.send_json(safe_rows(c.execute("SELECT pr.*,p.name product_name,r.name reward_product_name FROM promotions pr "
                        "LEFT JOIN products p ON p.id=pr.product_id LEFT JOIN products r ON r.id=pr.reward_product_id "
                        "ORDER BY pr.active DESC,pr.name").fetchall()))
            if path == "/api/promotion-options":
                with persistence_port.connect(DB_PATH) as c:
                    products = safe_rows(c.execute("SELECT id,sku,name,category FROM products WHERE active=1 ORDER BY name").fetchall())
                    categories = [row[0] for row in c.execute("SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category")]
                    return self.send_json({"products":products,"categories":categories})
            if path == "/api/cash-register":
                with persistence_port.connect(DB_PATH) as c:
                    return self.send_json(self.register_summary(c))
            if path == "/api/invoices":
                term = query.get("term", [""])[0].strip()
                with persistence_port.connect(DB_PATH) as c:
                    rows = c.execute("SELECT i.number invoice_number,i.issued_at,s.number sale_number,s.customer_name,s.customer_nit,s.total,s.payment_method "
                        "FROM invoices i JOIN sales s ON s.id=i.sale_id WHERE (?='' OR i.number LIKE ? OR s.customer_name LIKE ? OR s.number LIKE ?) "
                        "ORDER BY i.id DESC LIMIT 200",(term,f"%{term}%",f"%{term}%",f"%{term}%")).fetchall()
                    return self.send_json(safe_rows(rows))
            if path.startswith("/api/invoices/"):
                invoice_key = path.rsplit("/",1)[-1]
                with persistence_port.connect(DB_PATH) as c:
                    detail = self.invoice_detail(c, invoice_key)
                    if not detail:
                        return self.send_error_response("No se encontró la factura.", HTTPStatus.NOT_FOUND)
                    return self.send_json(detail)
            if path == "/api/returns":
                with persistence_port.connect(DB_PATH) as c:
                    rows = c.execute("SELECT r.*,s.number invoice_number,s.customer_name FROM returns r JOIN sales s ON s.id=r.sale_id ORDER BY r.id DESC LIMIT 300").fetchall()
                    return self.send_json(safe_rows(rows))
            if path == "/api/purchases":
                with persistence_port.connect(DB_PATH) as c:
                    rows = c.execute("SELECT pu.*,su.business_name supplier_name,u.display_name user_name FROM purchases pu "
                        "JOIN suppliers su ON su.id=pu.supplier_id JOIN users u ON u.id=pu.created_by ORDER BY pu.id DESC LIMIT 300").fetchall()
                    return self.send_json(safe_rows(rows))
            if path == "/api/reports":
                return self.send_json(self.report_data(query.get("from",[""])[0],query.get("to",[""])[0]))
            if path == "/api/qr/lookup":
                payload = query.get("payload",[""])[0]
                return self.send_json(self.lookup_qr(payload))
            if path == "/api/promotions/options":
                with persistence_port.connect(DB_PATH) as c:
                    return self.send_json(safe_rows(c.execute("SELECT id,code,name,type,category,product_id,min_qty,discount_percent,wholesale_price,reward_product_id,voucher_amount,points_per_unit FROM promotions WHERE active=1 ORDER BY name").fetchall()))
            price_match = re.match(r"^/api/products/(\d+)/prices$",path)
            if price_match:
                with persistence_port.connect(DB_PATH) as c:
                    rows = c.execute("SELECT id,cost,sale_price,effective_from,effective_to FROM product_prices WHERE product_id=? ORDER BY effective_from DESC,id DESC",(int(price_match.group(1)),)).fetchall()
                    return self.send_json(safe_rows(rows))
        except (sqlite3.Error, ValueError) as exc:
            return self.send_error_response(self.db_error(exc), HTTPStatus.BAD_REQUEST)
        return self.send_error_response("Ruta no encontrada.", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
        except ValueError as exc:
            return self.send_error_response(str(exc))
        if path == "/api/login":
            username = str(payload.get("username","")).strip()
            password = str(payload.get("password",""))
            with persistence_port.connect(DB_PATH) as c:
                user = c.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE AND active=1",(username,)).fetchone()
                if not user or not database.check_password(password,user["password_hash"]):
                    return self.send_error_response("Usuario o contraseña incorrectos.",HTTPStatus.UNAUTHORIZED)
                token = secrets.token_urlsafe(32)
                c.execute("DELETE FROM sessions WHERE expires_at<=?",(now(),))
                c.execute("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES (?,?,?,?)",
                    (hashlib.sha256(token.encode("ascii")).hexdigest(),user["id"],database.stamp(database.now_utc()+timedelta(hours=SESSION_HOURS)),now()))
                user_data = {"id":user["id"],"username":user["username"],"display_name":user["display_name"]}
            self.audit(user_data["id"],"inicio de sesión","usuario",user_data["id"])
            return self.send_json({"user":user_data},headers={"Set-Cookie":f"rincon_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS*3600}"})
        user = self.require_user()
        if not user:
            return
        try:
            if path == "/api/logout":
                token = self.cookie_value("rincon_session")
                if token:
                    with persistence_port.connect(DB_PATH) as c:
                        c.execute("DELETE FROM sessions WHERE token_hash=?",(hashlib.sha256(token.encode("ascii")).hexdigest(),))
                return self.send_json({"ok":True},headers={"Set-Cookie":"rincon_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
            if path in ("/api/clients","/api/suppliers","/api/products","/api/promotions"):
                collection = path.rsplit("/",1)[-1]
                record_id = self.create_catalog(collection,payload,user["id"])
                return self.send_json({"id":record_id,"ok":True},HTTPStatus.CREATED)
            if path == "/api/cash-register/open":
                return self.open_register(payload,user["id"])
            if path == "/api/cash-register/close":
                return self.close_register(payload,user["id"])
            if path == "/api/sales":
                return self.create_sale(payload,user["id"])
            if path == "/api/returns":
                return self.create_return(payload,user["id"])
            if path == "/api/purchases":
                return self.create_purchase(payload,user["id"])
        except (ValueError,sqlite3.IntegrityError,sqlite3.Error) as exc:
            return self.send_error_response(self.db_error(exc),HTTPStatus.BAD_REQUEST)
        return self.send_error_response("Ruta no encontrada.",HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        user = self.require_user()
        if not user:
            return
        try:
            payload = self.read_json()
            collection,record_id = self.catalog_path(urlparse(self.path).path)
            if not collection:
                return self.send_error_response("Ruta no encontrada.",HTTPStatus.NOT_FOUND)
            self.update_catalog(collection,record_id,payload,user["id"])
            return self.send_json({"ok":True})
        except (ValueError,sqlite3.IntegrityError,sqlite3.Error) as exc:
            return self.send_error_response(self.db_error(exc),HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        user = self.require_user()
        if not user:
            return
        collection,record_id = self.catalog_path(urlparse(self.path).path)
        if not collection:
            return self.send_error_response("Ruta no encontrada.",HTTPStatus.NOT_FOUND)
        table = {"clients":"clients","suppliers":"suppliers","products":"products","promotions":"promotions"}[collection]
        with persistence_port.connect(DB_PATH) as c:
            row = c.execute(f"SELECT active FROM {table} WHERE id=?",(record_id,)).fetchone()
            if not row:
                return self.send_error_response("Registro no encontrado.",HTTPStatus.NOT_FOUND)
            active = 0 if row["active"] else 1
            c.execute(f"UPDATE {table} SET active=?,updated_at=? WHERE id=?",(active,now(),record_id))
        self.audit(user["id"],"desactivar" if not active else "reactivar",collection,record_id)
        return self.send_json({"ok":True,"active":bool(active)})

    def create_catalog(self, collection: str, data: dict, user_id: int) -> int:
        now_value = now()
        with persistence_port.connect(DB_PATH) as c:
            if collection == "clients":
                cursor = c.execute("INSERT INTO clients(code,name,nit,phone,email,address,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (self.need(data,"code","código"),self.need(data,"name","nombre"),str(data.get("nit","")).strip(),str(data.get("phone","")).strip(),str(data.get("email","")).strip(),str(data.get("address","")).strip(),now_value,now_value))
            elif collection == "suppliers":
                cursor = c.execute("INSERT INTO suppliers(code,business_name,contact_name,nit,phone,email,address,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (self.need(data,"code","código"),self.need(data,"business_name","nombre comercial"),str(data.get("contact_name","")).strip(),str(data.get("nit","")).strip(),str(data.get("phone","")).strip(),str(data.get("email","")).strip(),str(data.get("address","")).strip(),now_value,now_value))
            elif collection == "products":
                cursor = c.execute("INSERT INTO products(sku,name,category,description,stock,supplier_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (self.need(data,"sku","SKU"),self.need(data,"name","nombre"),self.need(data,"category","categoría"),str(data.get("description","")).strip(),self.numeric(data,"stock","existencia"),data.get("supplier_id") or None,now_value,now_value))
                c.execute("INSERT INTO product_prices(product_id,cost,sale_price,effective_from) VALUES (?,?,?,?)",
                    (cursor.lastrowid,self.numeric(data,"cost","costo"),self.numeric(data,"sale_price","precio de venta"),now_value))
            else:
                cursor = self.save_promotion(c,data,None,now_value)
            record_id = cursor.lastrowid
        self.audit(user_id,"crear",collection,record_id)
        return record_id

    def update_catalog(self, collection: str, record_id: int, data: dict, user_id: int) -> None:
        now_value = now()
        table = {"clients":"clients","suppliers":"suppliers","products":"products","promotions":"promotions"}[collection]
        with persistence_port.connect(DB_PATH) as c:
            if not c.execute(f"SELECT id FROM {table} WHERE id=?",(record_id,)).fetchone():
                raise ValueError("Registro no encontrado.")
            if collection == "clients":
                c.execute("UPDATE clients SET code=?,name=?,nit=?,phone=?,email=?,address=?,updated_at=? WHERE id=?",
                    (self.need(data,"code","código"),self.need(data,"name","nombre"),str(data.get("nit","")).strip(),str(data.get("phone","")).strip(),str(data.get("email","")).strip(),str(data.get("address","")).strip(),now_value,record_id))
            elif collection == "suppliers":
                c.execute("UPDATE suppliers SET code=?,business_name=?,contact_name=?,nit=?,phone=?,email=?,address=?,updated_at=? WHERE id=?",
                    (self.need(data,"code","código"),self.need(data,"business_name","nombre comercial"),str(data.get("contact_name","")).strip(),str(data.get("nit","")).strip(),str(data.get("phone","")).strip(),str(data.get("email","")).strip(),str(data.get("address","")).strip(),now_value,record_id))
            elif collection == "products":
                c.execute("UPDATE products SET sku=?,name=?,category=?,description=?,stock=?,supplier_id=?,updated_at=? WHERE id=?",
                    (self.need(data,"sku","SKU"),self.need(data,"name","nombre"),self.need(data,"category","categoría"),str(data.get("description","")).strip(),self.numeric(data,"stock","existencia"),data.get("supplier_id") or None,now_value,record_id))
                cost = self.numeric(data,"cost","costo")
                sale = self.numeric(data,"sale_price","precio de venta")
                current = c.execute("SELECT cost,sale_price FROM product_prices WHERE product_id=? AND effective_to IS NULL",(record_id,)).fetchone()
                if not current:
                    c.execute("INSERT INTO product_prices(product_id,cost,sale_price,effective_from) VALUES (?,?,?,?)",(record_id,cost,sale,now_value))
                elif current["cost"] != cost or current["sale_price"] != sale:
                    c.execute("UPDATE product_prices SET effective_to=? WHERE product_id=? AND effective_to IS NULL",(now_value,record_id))
                    c.execute("INSERT INTO product_prices(product_id,cost,sale_price,effective_from) VALUES (?,?,?,?)",(record_id,cost,sale,now_value))
            else:
                self.save_promotion(c,data,record_id,now_value)
        self.audit(user_id,"actualizar",collection,record_id)

    def save_promotion(self,c,data:dict,record_id:int|None,now_value:str):
        code=self.need(data,"code","código de promoción")
        name=self.need(data,"name","nombre")
        kind=str(data.get("type",""))
        if kind not in {"discount","free_product","gift_voucher","half_second","wholesale","points"}:
            raise ValueError("Selecciona un tipo de promoción válido.")
        values=(code,name,kind,str(data.get("category","")).strip(),data.get("product_id") or None,
            self.numeric(data,"min_qty","cantidad mínima",0.01),self.numeric(data,"discount_percent","descuento porcentual"),
            self.numeric(data,"wholesale_price","precio por mayoreo"),data.get("reward_product_id") or None,
            self.numeric(data,"voucher_amount","valor del vale"),int(self.numeric(data,"points_per_unit","puntos por unidad")),
            int(bool(data.get("active"))),str(data.get("starts_at","")).strip() or None,str(data.get("ends_at","")).strip() or None,now_value)
        if record_id:
            c.execute("UPDATE promotions SET code=?,name=?,type=?,category=?,product_id=?,min_qty=?,discount_percent=?,wholesale_price=?,reward_product_id=?,voucher_amount=?,points_per_unit=?,active=?,starts_at=?,ends_at=?,updated_at=? WHERE id=?",values+(record_id,))
            return c.execute("SELECT id FROM promotions WHERE id=?",(record_id,))
        return c.execute("INSERT INTO promotions(code,name,type,category,product_id,min_qty,discount_percent,wholesale_price,reward_product_id,voucher_amount,points_per_unit,active,starts_at,ends_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",values+(now_value,))

    def register_summary(self,c):
        register=c.execute("SELECT cr.*,u.display_name opened_by_name FROM cash_registers cr JOIN users u ON u.id=cr.opened_by WHERE cr.status='OPEN' ORDER BY cr.id DESC LIMIT 1").fetchone()
        if not register:
            return {"is_open":False}
        cash_sales=c.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE register_id=? AND payment_method='Efectivo' AND status='COMPLETADA'",(register["id"],)).fetchone()[0]
        cash_returns=c.execute("SELECT COALESCE(SUM(refund_amount),0) FROM returns WHERE register_id=? AND payment_method='Efectivo'",(register["id"],)).fetchone()[0]
        card=c.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE register_id=? AND payment_method!='Efectivo' AND status='COMPLETADA'",(register["id"],)).fetchone()[0]
        return {"is_open":True,"id":register["id"],"opened_at":register["opened_at"],"opened_by":register["opened_by_name"],
            "opening_amount":register["opening_amount"],"cash_sales":rounded(cash_sales),"cash_returns":rounded(cash_returns),
            "noncash_sales":rounded(card),"expected_cash":rounded(register["opening_amount"]+cash_sales-cash_returns)}

    def open_register(self,payload,user_id):
        amount=self.numeric(payload,"opening_amount","fondo de apertura")
        with persistence_port.connect(DB_PATH) as c:
            if c.execute("SELECT id FROM cash_registers WHERE status='OPEN'").fetchone():
                return self.send_error_response("Ya hay una caja abierta.")
            cursor=c.execute("INSERT INTO cash_registers(opened_by,opened_at,opening_amount,status) VALUES (?,?,?,'OPEN')",(user_id,now(),amount))
            register_id=cursor.lastrowid
        self.audit(user_id,"apertura","caja",register_id,f"Fondo Q{amount:.2f}")
        return self.send_json({"ok":True,"id":register_id},HTTPStatus.CREATED)

    def close_register(self,payload,user_id):
        counted=self.numeric(payload,"counted_amount","efectivo contado")
        with persistence_port.connect(DB_PATH) as c:
            register=c.execute("SELECT id FROM cash_registers WHERE status='OPEN'").fetchone()
            if not register:
                return self.send_error_response("No hay una caja abierta.")
            summary=self.register_summary(c)
            difference=rounded(counted-summary["expected_cash"])
            c.execute("UPDATE cash_registers SET status='CLOSED',closed_by=?,closed_at=?,counted_amount=?,expected_cash=?,difference=? WHERE id=?",
                (user_id,now(),counted,summary["expected_cash"],difference,register["id"]))
        self.audit(user_id,"cierre","caja",register["id"],f"Esperado Q{summary['expected_cash']:.2f}; contado Q{counted:.2f}; diferencia Q{difference:.2f}")
        return self.send_json({"ok":True,"expected_cash":summary["expected_cash"],"counted_amount":counted,"difference":difference})

    def create_sale(self,payload,user_id):
        lines=payload.get("lines")
        if not isinstance(lines,list) or not lines:
            raise ValueError("Agrega al menos un producto a la venta.")
        payment=str(payload.get("payment_method",""))
        if payment not in PAYMENT_METHODS:
            raise ValueError("Selecciona efectivo, tarjeta de crédito o tarjeta de débito.")
        quantities={}
        for line in lines:
            try: product_id=int(line.get("product_id")); qty=float(line.get("quantity",0))
            except (TypeError,ValueError): raise ValueError("Revisa producto y cantidad en la venta.")
            if qty<=0: raise ValueError("Las cantidades deben ser mayores que cero.")
            quantities[product_id]=quantities.get(product_id,0)+qty
        with persistence_port.connect(DB_PATH) as c:
            c.execute("BEGIN IMMEDIATE")
            register=c.execute("SELECT id FROM cash_registers WHERE status='OPEN'").fetchone()
            if not register:
                raise ValueError("Abre la caja antes de registrar una venta.")
            client_id=payload.get("client_id") or None
            client=c.execute("SELECT * FROM clients WHERE id=? AND active=1",(client_id,)).fetchone() if client_id else None
            products={}
            for product_id,qty in quantities.items():
                product=c.execute("SELECT p.*,pp.cost,pp.sale_price FROM products p LEFT JOIN product_prices pp ON pp.product_id=p.id AND pp.effective_to IS NULL WHERE p.id=? AND p.active=1",(product_id,)).fetchone()
                if not product: raise ValueError("Un producto ya no está disponible.")
                if product["sale_price"] is None: raise ValueError(f"{product['name']} no tiene precio vigente.")
                if product["stock"]<qty: raise ValueError(f"Existencia insuficiente para {product['name']}. Disponible: {product['stock']:g}.")
                products[product_id]=product
            current=now()
            promotions=c.execute("SELECT * FROM promotions WHERE active=1 AND (starts_at IS NULL OR date(starts_at)<=date(?)) AND (ends_at IS NULL OR date(ends_at)>=date(?)) ORDER BY id",(current,current)).fetchall()
            category_qty={}
            for product_id,qty in quantities.items():
                cat=products[product_id]["category"]; category_qty[cat]=category_qty.get(cat,0)+qty
            sale_lines=[]; line_discount=0.0; earned=0; applied=[]; free_quantities={}
            for product_id,qty in quantities.items():
                product=products[product_id]; price=float(product["sale_price"]); subtotal=rounded(qty*price); discount=0.0; promo_id=None
                matches=[p for p in promotions if promotion_rules.applies_to(p,product_id,product["category"])]
                for promotion in matches:
                    if promotion["type"]=="points":
                        earned += promotion_rules.points_for(qty,promotion)
                        if promotion["points_per_unit"]: applied.append(promotion)
                discount,price_rule=promotion_rules.line_discount(qty,price,category_qty.get(product["category"],0),matches)
                if price_rule:
                    promo_id=price_rule["id"]; applied.append(price_rule)
                sale_lines.append({"product":product,"quantity":qty,"price":price,"subtotal":subtotal,"discount":discount,
                    "total":rounded(subtotal-discount),"free":False,"promotion_id":promo_id})
                line_discount += discount
                for promotion in matches:
                    if promotion["type"]=="free_product" and promotion_rules.qualifies(qty,promotion["min_qty"]) and promotion["reward_product_id"]:
                        reward_id=promotion["reward_product_id"]; free_quantities[reward_id]=free_quantities.get(reward_id,0)+1
                        applied.append(promotion)
                    if promotion["type"]=="gift_voucher" and promotion_rules.qualifies(qty,promotion["min_qty"]):
                        if not any(p["type"]=="gift_voucher" for p in applied): applied.append(promotion)
            for reward_id,qty in free_quantities.items():
                reward=c.execute("SELECT p.*,pp.sale_price,pp.cost FROM products p LEFT JOIN product_prices pp ON pp.product_id=p.id AND pp.effective_to IS NULL WHERE p.id=? AND p.active=1",(reward_id,)).fetchone()
                if not reward: raise ValueError("El producto de regalo de una promoción no está disponible.")
                products[reward_id]=reward
                price=float(reward["sale_price"] or 0)
                sale_lines.append({"product":reward,"quantity":qty,"price":price,"subtotal":rounded(qty*price),"discount":rounded(qty*price),"total":0.0,"free":True,
                    "promotion_id":next((p["id"] for p in applied if p["type"]=="free_product"),None)})
            total_quantities={}
            for row in sale_lines:
                product_id=row["product"]["id"]
                total_quantities[product_id]=total_quantities.get(product_id,0)+row["quantity"]
            for product_id,qty in total_quantities.items():
                product=products[product_id]
                if product["stock"]<qty:
                    raise ValueError(f"Existencia insuficiente para {product['name']} incluyendo los productos de regalo. Disponible: {product['stock']:g}.")
            subtotal=rounded(sum(row["subtotal"] for row in sale_lines))
            line_discount=rounded(line_discount+sum(row["discount"] for row in sale_lines if row["free"]))
            voucher_code=str(payload.get("voucher_code","")).strip().upper()
            voucher=None; voucher_discount=0.0
            if voucher_code:
                voucher=c.execute("SELECT * FROM vouchers WHERE code=? AND status='DISPONIBLE'",(voucher_code,)).fetchone()
                if not voucher: raise ValueError("El vale no existe o ya fue utilizado.")
                if voucher["client_id"] and voucher["client_id"]!=client_id: raise ValueError("Ese vale pertenece a otro cliente.")
                voucher_discount=min(float(voucher["amount"]),max(0,subtotal-line_discount))
            points_available=int(client["loyalty_points"]) if client else 0
            points_redeemed=min(points_available,int(max(0,subtotal-line_discount-voucher_discount))) if client and payload.get("use_points") else 0
            points_discount=float(points_redeemed)
            total=rounded(max(0,subtotal-line_discount-voucher_discount-points_discount))
            amount_received=total
            if payment=="Efectivo":
                amount_received=self.numeric(payload,"amount_received","efectivo recibido")
                if amount_received<total: raise ValueError(f"El efectivo recibido debe ser al menos Q{total:.2f}.")
            change=rounded(max(0,amount_received-total)) if payment=="Efectivo" else 0
            customer_name=(client["name"] if client else str(payload.get("customer_name","Consumidor final")).strip() or "Consumidor final")
            customer_nit=(client["nit"] if client else str(payload.get("customer_nit","CF")).strip() or "CF")
            customer_address=(client["address"] if client else str(payload.get("customer_address","")).strip())
            cursor=c.execute("INSERT INTO sales(number,register_id,client_id,customer_name,customer_nit,customer_address,subtotal,line_discount,voucher_discount,points_discount,discount_total,total,payment_method,amount_received,change_due,points_earned,points_redeemed,created_by,created_at) VALUES ('PENDIENTE',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (register["id"],client_id,customer_name,customer_nit,customer_address,subtotal,line_discount,voucher_discount,points_discount,rounded(line_discount+voucher_discount+points_discount),total,payment,amount_received,change,earned,points_redeemed,user_id,current))
            sale_id=cursor.lastrowid; sale_number=f"VT-{sale_id:06d}"; invoice_number=f"F-{sale_id:06d}"
            c.execute("UPDATE sales SET number=? WHERE id=?",(sale_number,sale_id))
            for row in sale_lines:
                p=row["product"]
                if p["stock"]<row["quantity"]: raise ValueError(f"Existencia insuficiente para {p['name']} incluyendo los productos de regalo.")
                c.execute("INSERT INTO sale_lines(sale_id,product_id,sku,product_name,category,quantity,unit_price,line_subtotal,discount_amount,line_total,is_free,promotion_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (sale_id,p["id"],p["sku"],p["name"],p["category"],row["quantity"],row["price"],row["subtotal"],row["discount"],row["total"],int(row["free"]),row["promotion_id"]))
                c.execute("UPDATE products SET stock=stock-?,updated_at=? WHERE id=?",(row["quantity"],current,p["id"]))
            if client and (earned or points_redeemed):
                c.execute("UPDATE clients SET loyalty_points=loyalty_points+?-? WHERE id=?",(earned,points_redeemed,client_id))
                if earned: c.execute("INSERT INTO loyalty_transactions(client_id,sale_id,points_delta,description,created_at) VALUES (?,?,?,?,?)",(client_id,sale_id,earned,"Puntos ganados en "+sale_number,current))
                if points_redeemed: c.execute("INSERT INTO loyalty_transactions(client_id,sale_id,points_delta,description,created_at) VALUES (?,?,?,?,?)",(client_id,sale_id,-points_redeemed,"Puntos usados en "+sale_number,current))
            if voucher:
                c.execute("UPDATE vouchers SET status='USADO',redeemed_sale_id=?,redeemed_at=? WHERE id=?",(sale_id,current,voucher["id"]))
            gift_promo=next((p for p in applied if p["type"]=="gift_voucher"),None)
            issued_voucher=None
            if gift_promo and float(gift_promo["voucher_amount"])>0:
                issued_voucher=f"VALE-{sale_id:06d}"
                c.execute("INSERT INTO vouchers(code,issued_sale_id,client_id,amount,created_at) VALUES (?,?,?,?,?)",(issued_voucher,sale_id,client_id,float(gift_promo["voucher_amount"]),current))
            promo_types=[]
            seen=set()
            for promo in applied:
                label=f"{promo['name']} ({promo['type']})"
                if label not in seen: promo_types.append(label); seen.add(label)
            promotion_text="; ".join(promo_types) if promo_types else "Sin promoción"
            qr_promotion=next((p for p in applied if p["type"]!="points"),applied[0] if applied else None)
            promo_code=qr_promotion["code"] if qr_promotion else "SIN-PROMO"
            promo_type=qr_promotion["type"] if qr_promotion else "sin-promocion"
            qr_payload=f"RINCON|{invoice_number}|{promo_code}|{promo_type}"
            c.execute("INSERT INTO invoices(sale_id,number,issued_at,qr_payload,promotion_text) VALUES (?,?,?,?,?)",(sale_id,invoice_number,current,qr_payload,promotion_text))
        self.audit(user_id,"venta y factura","invoice",sale_id,f"{invoice_number}; total Q{total:.2f}")
        with persistence_port.connect(DB_PATH) as c:
            detail=self.invoice_detail(c,invoice_number)
            detail["issued_voucher"]=issued_voucher
            detail["applied_promotions"]=promo_types
            return self.send_json(detail,HTTPStatus.CREATED)

    def invoice_detail(self,c,invoice_key):
        row=c.execute("SELECT i.id invoice_id,i.number invoice_number,i.issued_at,i.qr_payload,i.promotion_text,s.*,u.display_name cashier "
            "FROM invoices i JOIN sales s ON s.id=i.sale_id JOIN users u ON u.id=s.created_by WHERE i.number=? OR s.number=? OR CAST(i.id AS TEXT)=?",
            (invoice_key,invoice_key,invoice_key)).fetchone()
        if not row:return None
        result=dict(row)
        result["lines"]=safe_rows(c.execute("SELECT sl.*,(SELECT COALESCE(SUM(r.quantity),0) FROM returns r WHERE r.sale_line_id=sl.id) returned_quantity FROM sale_lines sl WHERE sl.sale_id=? ORDER BY sl.id",(row["id"],)).fetchall())
        result["qr_matrix"]=qr_encoder_port.encode(row["qr_payload"])
        result["issued_voucher"]=None
        voucher=c.execute("SELECT code,amount,status FROM vouchers WHERE issued_sale_id=? ORDER BY id LIMIT 1",(row["id"],)).fetchone()
        if voucher:result["issued_voucher"]=dict(voucher)
        return result

    def create_return(self,payload,user_id):
        try: line_id=int(payload.get("sale_line_id")); qty=float(payload.get("quantity",0))
        except (TypeError,ValueError): raise ValueError("Selecciona la línea de factura y la cantidad a devolver.")
        reason=str(payload.get("reason","")); payment=str(payload.get("payment_method",""))
        if reason not in {"Daño","Vencimiento"}: raise ValueError("Selecciona si el producto está dañado o vencido.")
        if payment not in PAYMENT_METHODS: raise ValueError("Selecciona el medio de reembolso.")
        if qty<=0: raise ValueError("La cantidad debe ser mayor que cero.")
        with persistence_port.connect(DB_PATH) as c:
            c.execute("BEGIN IMMEDIATE")
            register=c.execute("SELECT id FROM cash_registers WHERE status='OPEN'").fetchone()
            if not register: raise ValueError("Abre la caja antes de registrar una devolución.")
            line=c.execute("SELECT sl.*,s.id sale_id,s.number sale_number,s.status FROM sale_lines sl JOIN sales s ON s.id=sl.sale_id WHERE sl.id=?",(line_id,)).fetchone()
            if not line or line["status"]!='COMPLETADA': raise ValueError("No se encontró esa línea de venta.")
            already=c.execute("SELECT COALESCE(SUM(quantity),0) FROM returns WHERE sale_line_id=?",(line_id,)).fetchone()[0]
            remaining=round(float(line["quantity"])-float(already),4)
            if qty>remaining: raise ValueError(f"La cantidad supera lo pendiente de devolver ({remaining:g}).")
            refund=rounded(float(line["line_total"])/float(line["quantity"])*qty)
            current=now(); number=f"DEV-{int(c.execute('SELECT COALESCE(MAX(id),0)+1 FROM returns').fetchone()[0]):06d}"
            cursor=c.execute("INSERT INTO returns(number,sale_id,sale_line_id,product_id,product_name,sku,quantity,reason,refund_amount,payment_method,register_id,processed_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (number,line["sale_id"],line_id,line["product_id"],line["product_name"],line["sku"],qty,reason,refund,payment,register["id"],user_id,current))
            return_id=cursor.lastrowid
        self.audit(user_id,"devolución","return",return_id,f"{number}; {reason}; reembolso Q{refund:.2f}")
        return self.send_json({"ok":True,"number":number,"refund_amount":refund,"stock_reentered":False},HTTPStatus.CREATED)

    def create_purchase(self,payload,user_id):
        try:supplier_id=int(payload.get("supplier_id"))
        except (TypeError,ValueError):raise ValueError("Selecciona un proveedor.")
        lines=payload.get("lines")
        if not isinstance(lines,list) or not lines:raise ValueError("Agrega al menos un producto a la compra.")
        with persistence_port.connect(DB_PATH) as c:
            c.execute("BEGIN IMMEDIATE")
            supplier=c.execute("SELECT id FROM suppliers WHERE id=? AND active=1",(supplier_id,)).fetchone()
            if not supplier:raise ValueError("Selecciona un proveedor activo.")
            current=now(); details=[]; total=0.0
            for item in lines:
                try:product_id=int(item.get("product_id"));qty=float(item.get("quantity",0));unit_cost=float(item.get("unit_cost",-1))
                except (TypeError,ValueError):raise ValueError("Revisa cantidades y costos de la compra.")
                if qty<=0 or unit_cost<0:raise ValueError("La cantidad debe ser positiva y el costo no puede ser negativo.")
                product=c.execute("SELECT id,sku,name FROM products WHERE id=? AND active=1",(product_id,)).fetchone()
                if not product:raise ValueError("Un producto seleccionado ya no está disponible.")
                line_total=rounded(qty*unit_cost);total=rounded(total+line_total)
                details.append((product,qty,unit_cost,line_total))
            cursor=c.execute("INSERT INTO purchases(number,supplier_id,total,created_by,created_at) VALUES ('PENDIENTE',?,?,?,?)",(supplier_id,total,user_id,current))
            purchase_id=cursor.lastrowid; number=f"COMP-{purchase_id:06d}"
            c.execute("UPDATE purchases SET number=? WHERE id=?",(number,purchase_id))
            for product,qty,cost,line_total in details:
                c.execute("INSERT INTO purchase_lines(purchase_id,product_id,sku,product_name,quantity,unit_cost,line_total) VALUES (?,?,?,?,?,?,?)",(purchase_id,product["id"],product["sku"],product["name"],qty,cost,line_total))
                c.execute("UPDATE products SET stock=stock+?,updated_at=? WHERE id=?",(qty,current,product["id"]))
                price=c.execute("SELECT cost,sale_price FROM product_prices WHERE product_id=? AND effective_to IS NULL",(product["id"],)).fetchone()
                if price and price["cost"]!=cost:
                    c.execute("UPDATE product_prices SET effective_to=? WHERE product_id=? AND effective_to IS NULL",(current,product["id"]))
                    c.execute("INSERT INTO product_prices(product_id,cost,sale_price,effective_from) VALUES (?,?,?,?)",(product["id"],cost,price["sale_price"],current))
        self.audit(user_id,"ingreso de compra","purchase",purchase_id,f"{number}; total Q{total:.2f}")
        return self.send_json({"ok":True,"id":purchase_id,"number":number,"total":total},HTTPStatus.CREATED)

    def report_data(self,start:str,end:str):
        where="date(created_at) BETWEEN date(?) AND date(?)"
        start=start or "2000-01-01";end=end or "2999-12-31"
        with persistence_port.connect(DB_PATH) as c:
            sales=safe_rows(c.execute(f"SELECT payment_method,COUNT(*) transactions,COALESCE(SUM(total),0) total FROM sales WHERE {where} AND status='COMPLETADA' GROUP BY payment_method",(start,end)).fetchall())
            totals=c.execute(f"SELECT COUNT(*) count,COALESCE(SUM(total),0) total FROM sales WHERE {where} AND status='COMPLETADA'",(start,end)).fetchone()
            returns=c.execute(f"SELECT COUNT(*) count,COALESCE(SUM(refund_amount),0) total FROM returns WHERE {where}",(start,end)).fetchone()
            return_rows=safe_rows(c.execute(f"SELECT r.number,r.created_at,r.sku,r.product_name,r.quantity,r.reason,r.refund_amount,s.number invoice_number,s.customer_name FROM returns r JOIN sales s ON s.id=r.sale_id WHERE date(r.created_at) BETWEEN date(?) AND date(?) ORDER BY r.id DESC",(start,end)).fetchall())
            clients=safe_rows(c.execute("SELECT c.code,c.name,c.nit,c.phone,c.loyalty_points,COUNT(s.id) purchases,COALESCE(SUM(s.total),0) total FROM clients c LEFT JOIN sales s ON s.client_id=c.id AND date(s.created_at) BETWEEN date(?) AND date(?) GROUP BY c.id ORDER BY total DESC,c.name",(start,end)).fetchall())
            purchases=safe_rows(c.execute(f"SELECT p.number,p.created_at,su.business_name supplier_name,pl.sku,pl.product_name,pl.quantity,pl.unit_cost,pl.line_total FROM purchases p JOIN suppliers su ON su.id=p.supplier_id JOIN purchase_lines pl ON pl.purchase_id=p.id WHERE date(p.created_at) BETWEEN date(?) AND date(?) ORDER BY p.id DESC,pl.id",(start,end)).fetchall())
            purchase_total=c.execute(f"SELECT COALESCE(SUM(total),0) FROM purchases WHERE {where}",(start,end)).fetchone()[0]
            cash_closings=safe_rows(c.execute("SELECT cr.id,cr.opened_at,cr.closed_at,cr.opening_amount,cr.expected_cash,cr.counted_amount,cr.difference,u.display_name opened_by FROM cash_registers cr JOIN users u ON u.id=cr.opened_by WHERE date(cr.opened_at) BETWEEN date(?) AND date(?) ORDER BY cr.id DESC",(start,end)).fetchall())
            return {"from":start,"to":end,"sales":sales,"sales_count":totals["count"],"sales_total":rounded(totals["total"]),
                "return_count":returns["count"],"return_total":rounded(returns["total"]),"net_total":rounded(totals["total"]-returns["total"]),
                "returns":return_rows,"clients":clients,"purchases":purchases,"purchase_total":rounded(purchase_total),"cash_closings":cash_closings}

    def lookup_qr(self,payload:str):
        parts=payload.strip().split("|")
        if len(parts)<4 or parts[0]!="RINCON":
            return {"found":False,"message":"El código no corresponde a una factura del Rincón."}
        invoice_no=parts[1]
        with persistence_port.connect(DB_PATH) as c:
            row=c.execute("SELECT i.number,i.promotion_text,s.customer_name,s.created_at FROM invoices i JOIN sales s ON s.id=i.sale_id WHERE i.number=?",(invoice_no,)).fetchone()
            if not row:return {"found":False,"message":"No se encontró la factura asociada al código."}
            return {"found":True,"invoice_number":row["number"],"promotion":row["promotion_text"],"customer":row["customer_name"],"date":row["created_at"],"promo_code":parts[2],"promo_type":parts[3]}


def main():
    persistence_port.initialize_database(DB_PATH)
    server=ThreadingHTTPServer((HOST,PORT),AppHandler)
    print(f"La casa del rincón guatemalteco: http://127.0.0.1:{PORT}")
    print(f"Base relacional: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
