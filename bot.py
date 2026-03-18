# -*- coding: utf-8 -*-
"""
ConfigFlow / TracklessVPN Telegram Bot

Requirements:
    pip install -r requirements.txt

Run:
    export BOT_TOKEN="YOUR_BOT_TOKEN"
    export ADMIN_IDS="123456789"
    python bot.py

Notes:
    - همه چیز در یک فایل پایتون قرار گرفته است.
    - دیتابیس SQLite به صورت خودکار کنار فایل ساخته می‌شود.
    - برای دریافت پیام‌های ادمین، آیدی عددی ادمین را در ADMIN_IDS قرار دهید.
"""

import io
import os
import re
import html
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
import qrcode
import telebot
from telebot import types

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_IDS = {
    int(item.strip())
    for item in os.getenv("ADMIN_IDS", "123456789").split(",")
    if item.strip().isdigit()
}
DB_NAME = os.getenv("DB_NAME", "trackless_bot.db")

BRAND_TITLE = "TracklessVPN"
BOT_HANDLE = "@TracklessSell_bot"
CHANNEL_HANDLE = "@TracklessVPN"
DEFAULT_ADMIN_HANDLE = "@Tracklessvpnadmin"

if BOT_TOKEN == "YOUR_BOT_TOKEN":
    raise SystemExit("لطفاً BOT_TOKEN را در متغیر محیطی تنظیم کنید.")

if not ADMIN_IDS:
    raise SystemExit("لطفاً ADMIN_IDS را با آیدی عددی ادمین تنظیم کنید.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)
USER_STATE = {}

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


# ---------------------------
# Utilities
# ---------------------------
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def normalize_text_number(value: str) -> str:
    value = (value or "").translate(PERSIAN_DIGITS)
    value = value.replace(",", "").replace("٬", "").replace(" ", "")
    value = value.replace("تومان", "").replace("ریال", "")
    return value.strip()


def parse_int(value: str):
    cleaned = normalize_text_number(value)
    if not cleaned or not re.fullmatch(r"\d+", cleaned):
        return None
    return int(cleaned)


def fmt_price(amount: int) -> str:
    return f"{int(amount):,}"


def display_name(tg_user) -> str:
    name = " ".join([part for part in [tg_user.first_name or "", tg_user.last_name or ""] if part]).strip()
    return name or "ㅤ"


def display_username(username: str) -> str:
    return f"@{username}" if username else "@ ندارد"


def safe_support_url(raw_value: str):
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None
    if raw_value.startswith("http://") or raw_value.startswith("https://"):
        return raw_value
    raw_value = raw_value.replace("https://", "").replace("http://", "")
    raw_value = raw_value.replace("t.me/", "").replace("telegram.me/", "")
    raw_value = raw_value.replace("@", "").strip()
    if not raw_value:
        return None
    return f"https://t.me/{raw_value}"


def card_owner_or_placeholder(value: str) -> str:
    return value.strip() if value and value.strip() else "ثبت نشده"


def state_get(user_id: int):
    return USER_STATE.get(user_id)


def state_set(user_id: int, name: str, **data):
    USER_STATE[user_id] = {"name": name, "data": data}


def state_clear(user_id: int):
    USER_STATE.pop(user_id, None)


# ---------------------------
# Database
# ---------------------------
def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                balance INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS config_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                volume_gb INTEGER NOT NULL,
                duration_days INTEGER NOT NULL,
                price INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(type_id) REFERENCES config_types(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_id INTEGER NOT NULL,
                package_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                config_text TEXT NOT NULL,
                inquiry_link TEXT,
                reserved_payment_id INTEGER,
                sold_to INTEGER,
                purchase_id INTEGER,
                created_at TEXT NOT NULL,
                sold_at TEXT,
                FOREIGN KEY(type_id) REFERENCES config_types(id) ON DELETE CASCADE,
                FOREIGN KEY(package_id) REFERENCES packages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                package_id INTEGER,
                amount INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT NOT NULL,
                receipt_file_id TEXT,
                receipt_text TEXT,
                admin_note TEXT,
                created_at TEXT NOT NULL,
                approved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                package_id INTEGER NOT NULL,
                config_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        defaults = {
            "support_username": "",
            "payment_card": "",
            "payment_bank": "",
            "payment_owner": "",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row:
            return row["value"] or default
    return default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def upsert_user(tg_user):
    current_time = now_str()
    full_name = display_name(tg_user)
    username = tg_user.username or ""
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (tg_user.id,)
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE users SET full_name = ?, username = ?, last_seen_at = ? WHERE user_id = ?",
                (full_name, username, current_time, tg_user.id),
            )
        else:
            conn.execute(
                "INSERT INTO users (user_id, full_name, username, balance, joined_at, last_seen_at) "
                "VALUES (?, ?, ?, 0, ?, ?)",
                (tg_user.id, full_name, username, current_time, current_time),
            )


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def change_balance(user_id: int, delta: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (delta, user_id),
        )


def get_types():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM config_types ORDER BY id DESC").fetchall()


def get_type(type_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM config_types WHERE id = ?", (type_id,)).fetchone()


def add_type(name: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO config_types (name) VALUES (?)", (name.strip(),))


def update_type(type_id: int, name: str):
    with get_conn() as conn:
        conn.execute("UPDATE config_types SET name = ? WHERE id = ?", (name.strip(), type_id))


def can_delete_type(type_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM packages WHERE type_id = ?", (type_id,)
        ).fetchone()
        return bool(row and row["cnt"] == 0)


def delete_type(type_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM config_types WHERE id = ?", (type_id,))


def get_packages(type_id=None):
    sql = (
        "SELECT p.*, t.name AS type_name, "
        "(SELECT COUNT(*) FROM configs c "
        " WHERE c.package_id = p.id AND c.sold_to IS NULL AND c.reserved_payment_id IS NULL) AS available_count "
        "FROM packages p "
        "JOIN config_types t ON t.id = p.type_id "
    )
    params = []
    if type_id is not None:
        sql += "WHERE p.type_id = ? "
        params.append(type_id)
    sql += "ORDER BY p.id DESC"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_package(package_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT p.*, t.name AS type_name, "
            "(SELECT COUNT(*) FROM configs c "
            " WHERE c.package_id = p.id AND c.sold_to IS NULL AND c.reserved_payment_id IS NULL) AS available_count "
            "FROM packages p "
            "JOIN config_types t ON t.id = p.type_id "
            "WHERE p.id = ?",
            (package_id,),
        ).fetchone()


def add_package(type_id: int, name: str, volume_gb: int, duration_days: int, price: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO packages (type_id, name, volume_gb, duration_days, price, active) VALUES (?, ?, ?, ?, ?, 1)",
            (type_id, name.strip(), volume_gb, duration_days, price),
        )


def update_package(package_id: int, name: str, volume_gb: int, duration_days: int, price: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE packages SET name = ?, volume_gb = ?, duration_days = ?, price = ? WHERE id = ?",
            (name.strip(), volume_gb, duration_days, price, package_id),
        )


def delete_package(package_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))


def can_delete_package(package_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM configs WHERE package_id = ?", (package_id,)
        ).fetchone()
        return bool(row and row["cnt"] == 0)


def add_config(type_id: int, package_id: int, service_name: str, config_text: str, inquiry_link: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO configs (type_id, package_id, service_name, config_text, inquiry_link, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (type_id, package_id, service_name.strip(), config_text.strip(), inquiry_link.strip(), now_str()),
        )


def get_config(config_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT c.*, p.name AS package_name, p.volume_gb, p.duration_days, p.price, t.name AS type_name "
            "FROM configs c "
            "JOIN packages p ON p.id = c.package_id "
            "JOIN config_types t ON t.id = c.type_id "
            "WHERE c.id = ?",
            (config_id,),
        ).fetchone()


def get_remaining_stock_packages():
    with get_conn() as conn:
        return conn.execute(
            "SELECT p.id, p.name, p.volume_gb, p.duration_days, p.price, t.name AS type_name, "
            "COUNT(c.id) AS remaining_count "
            "FROM packages p "
            "JOIN config_types t ON t.id = p.type_id "
            "LEFT JOIN configs c ON c.package_id = p.id AND c.sold_to IS NULL AND c.reserved_payment_id IS NULL "
            "GROUP BY p.id "
            "ORDER BY p.id DESC"
        ).fetchall()


def get_remaining_configs_by_package(package_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT c.*, p.name AS package_name, p.volume_gb, p.duration_days, t.name AS type_name "
            "FROM configs c "
            "JOIN packages p ON p.id = c.package_id "
            "JOIN config_types t ON t.id = c.type_id "
            "WHERE c.package_id = ? AND c.sold_to IS NULL AND c.reserved_payment_id IS NULL "
            "ORDER BY c.id DESC",
            (package_id,),
        ).fetchall()


def create_wallet_purchase(user_id: int, package_id: int):
    with get_conn() as conn:
        pkg = conn.execute(
            "SELECT p.*, t.name AS type_name FROM packages p JOIN config_types t ON t.id = p.type_id WHERE p.id = ?",
            (package_id,),
        ).fetchone()
        if not pkg:
            return None, "این پکیج پیدا نشد."

        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            return None, "کاربر پیدا نشد."
        if user["balance"] < pkg["price"]:
            return None, "موجودی کیف پول شما برای این خرید کافی نیست."

        cfg = conn.execute(
            "SELECT * FROM configs WHERE package_id = ? AND sold_to IS NULL AND reserved_payment_id IS NULL ORDER BY id LIMIT 1",
            (package_id,),
        ).fetchone()
        if not cfg:
            return None, "در حال حاضر موجودی این سرویس به اتمام رسیده است."

        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (pkg["price"], user_id),
        )
        cur = conn.execute(
            "INSERT INTO purchases (user_id, package_id, config_id, amount, payment_method, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, package_id, cfg["id"], pkg["price"], "wallet", now_str()),
        )
        purchase_id = cur.lastrowid
        conn.execute(
            "UPDATE configs SET sold_to = ?, purchase_id = ?, sold_at = ? WHERE id = ?",
            (user_id, purchase_id, now_str(), cfg["id"]),
        )
    return get_purchase(purchase_id), None


def create_purchase_payment_with_reserve(user_id: int, package_id: int):
    with get_conn() as conn:
        pkg = conn.execute(
            "SELECT * FROM packages WHERE id = ?",
            (package_id,),
        ).fetchone()
        if not pkg:
            return None, "پکیج موردنظر پیدا نشد."

        cfg = conn.execute(
            "SELECT * FROM configs WHERE package_id = ? AND sold_to IS NULL AND reserved_payment_id IS NULL ORDER BY id LIMIT 1",
            (package_id,),
        ).fetchone()
        if not cfg:
            return None, "برای این پکیج فعلاً کانفیگ آماده تحویل موجود نیست."

        cur = conn.execute(
            "INSERT INTO payments (kind, user_id, package_id, amount, payment_method, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("purchase", user_id, package_id, pkg["price"], "card_to_card", "pending", now_str()),
        )
        payment_id = cur.lastrowid
        conn.execute(
            "UPDATE configs SET reserved_payment_id = ? WHERE id = ?",
            (payment_id, cfg["id"]),
        )
    return get_payment(payment_id), None


def create_wallet_charge_payment(user_id: int, amount: int):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO payments (kind, user_id, package_id, amount, payment_method, status, created_at) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?)",
            ("wallet", user_id, amount, "card_to_card", "pending", now_str()),
        )
        payment_id = cur.lastrowid
    return get_payment(payment_id)


def update_payment_receipt(payment_id: int, file_id: str = None, receipt_text: str = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE payments SET receipt_file_id = ?, receipt_text = ? WHERE id = ?",
            (file_id, (receipt_text or "").strip(), payment_id),
        )


def get_payment(payment_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT pay.*, u.full_name, u.username, "
            "p.name AS package_name, p.volume_gb, p.duration_days, t.name AS type_name, "
            "(SELECT service_name FROM configs WHERE reserved_payment_id = pay.id LIMIT 1) AS service_name "
            "FROM payments pay "
            "JOIN users u ON u.user_id = pay.user_id "
            "LEFT JOIN packages p ON p.id = pay.package_id "
            "LEFT JOIN config_types t ON t.id = p.type_id "
            "WHERE pay.id = ?",
            (payment_id,),
        ).fetchone()


def approve_wallet_charge(payment_id: int, admin_note: str):
    with get_conn() as conn:
        pay = conn.execute(
            "SELECT * FROM payments WHERE id = ? AND kind = 'wallet' AND status = 'pending'",
            (payment_id,),
        ).fetchone()
        if not pay:
            return None, "این درخواست قبلاً بررسی شده یا معتبر نیست."
        conn.execute(
            "UPDATE payments SET status = 'approved', admin_note = ?, approved_at = ? WHERE id = ?",
            (admin_note, now_str(), payment_id),
        )
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (pay["amount"], pay["user_id"]),
        )
    return get_payment(payment_id), None


def reject_wallet_charge(payment_id: int, admin_note: str):
    with get_conn() as conn:
        pay = conn.execute(
            "SELECT * FROM payments WHERE id = ? AND kind = 'wallet' AND status = 'pending'",
            (payment_id,),
        ).fetchone()
        if not pay:
            return None, "این درخواست قبلاً بررسی شده یا معتبر نیست."
        conn.execute(
            "UPDATE payments SET status = 'rejected', admin_note = ?, approved_at = ? WHERE id = ?",
            (admin_note, now_str(), payment_id),
        )
    return get_payment(payment_id), None


def approve_purchase_payment(payment_id: int, admin_note: str):
    with get_conn() as conn:
        pay = conn.execute(
            "SELECT * FROM payments WHERE id = ? AND kind = 'purchase' AND status = 'pending'",
            (payment_id,),
        ).fetchone()
        if not pay:
            return None, None, "این درخواست قبلاً بررسی شده یا معتبر نیست."

        cfg = conn.execute(
            "SELECT * FROM configs WHERE reserved_payment_id = ? LIMIT 1",
            (payment_id,),
        ).fetchone()
        if not cfg:
            return None, None, "کانفیگ رزروشده برای این پرداخت پیدا نشد."

        conn.execute(
            "UPDATE payments SET status = 'approved', admin_note = ?, approved_at = ? WHERE id = ?",
            (admin_note, now_str(), payment_id),
        )
        cur = conn.execute(
            "INSERT INTO purchases (user_id, package_id, config_id, amount, payment_method, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pay["user_id"], pay["package_id"], cfg["id"], pay["amount"], pay["payment_method"], now_str()),
        )
        purchase_id = cur.lastrowid
        conn.execute(
            "UPDATE configs SET sold_to = ?, purchase_id = ?, sold_at = ?, reserved_payment_id = NULL WHERE id = ?",
            (pay["user_id"], purchase_id, now_str(), cfg["id"]),
        )
    return get_payment(payment_id), get_purchase(purchase_id), None


def reject_purchase_payment(payment_id: int, admin_note: str):
    with get_conn() as conn:
        pay = conn.execute(
            "SELECT * FROM payments WHERE id = ? AND kind = 'purchase' AND status = 'pending'",
            (payment_id,),
        ).fetchone()
        if not pay:
            return None, "این درخواست قبلاً بررسی شده یا معتبر نیست."
        conn.execute(
            "UPDATE payments SET status = 'rejected', admin_note = ?, approved_at = ? WHERE id = ?",
            (admin_note, now_str(), payment_id),
        )
        conn.execute(
            "UPDATE configs SET reserved_payment_id = NULL WHERE reserved_payment_id = ?",
            (payment_id,),
        )
    return get_payment(payment_id), None


def get_purchase(purchase_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT pu.*, u.full_name, u.username, "
            "p.name AS package_name, p.volume_gb, p.duration_days, p.price, t.name AS type_name, "
            "c.service_name, c.config_text, c.inquiry_link "
            "FROM purchases pu "
            "JOIN users u ON u.user_id = pu.user_id "
            "JOIN packages p ON p.id = pu.package_id "
            "JOIN config_types t ON t.id = p.type_id "
            "JOIN configs c ON c.id = pu.config_id "
            "WHERE pu.id = ?",
            (purchase_id,),
        ).fetchone()


def get_user_purchases(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT pu.*, p.name AS package_name, p.volume_gb, p.duration_days, t.name AS type_name, "
            "c.service_name, c.config_text, c.inquiry_link "
            "FROM purchases pu "
            "JOIN packages p ON p.id = pu.package_id "
            "JOIN config_types t ON t.id = p.type_id "
            "JOIN configs c ON c.id = pu.config_id "
            "WHERE pu.user_id = ? ORDER BY pu.id DESC",
            (user_id,),
        ).fetchall()


# ---------------------------
# Text builders
# ---------------------------
def start_text(name: str) -> str:
    return (
        f"🌿 سلام {html.escape(name)} عزیز،\n\n"
        f"به ربات فروش کانفیگ شرایط نت ملی <b>{BRAND_TITLE}</b> خوش آمدی.\n"
        "اینجا می‌تونی خیلی راحت سرویس جدید بخری، سرویس‌های قبلی‌ات را ببینی و کیف پولت را مدیریت کنی.\n\n"
        f"🤖 بات فروش: {BOT_HANDLE}\n"
        f"🎭 ادمین: {DEFAULT_ADMIN_HANDLE}\n"
        f"📣 کانال: {CHANNEL_HANDLE}\n\n"
        "از منوی زیر یکی از گزینه‌ها را انتخاب کن 🌸"
    )


def profile_text(user_row) -> str:
    return (
        "👤 <b>پروفایل کاربری</b>\n\n"
        f"📱 نام: {html.escape(user_row['full_name'] or 'ㅤ')}\n"
        f"🔗 نام کاربری: {html.escape(display_username(user_row['username']))}\n"
        f"🆔 آیدی عددی: <code>{user_row['user_id']}</code>\n\n"
        f"💰 موجودی: <b>{fmt_price(user_row['balance'])}</b> تومان"
    )


def package_summary_text(pkg) -> str:
    return (
        "🧾 <b>پکیج انتخابی شما</b>\n\n"
        f"🚦 سرور: {html.escape(pkg['type_name'])}\n"
        f"📦 نام پکیج: {html.escape(pkg['name'])}\n"
        f"🔋 حجم سرویس: {pkg['volume_gb']} گیگ\n"
        f"⏰ مدت سرویس: {pkg['duration_days']} روز\n"
        f"💳 مبلغ: <b>{fmt_price(pkg['price'])}</b> تومان\n"
        f"📦 موجودی آماده تحویل: {pkg['available_count']} عدد\n\n"
        "لطفاً روش پرداخت را انتخاب کن:"
    )


def payment_card_text(amount: int) -> str:
    bank = get_setting("payment_bank")
    owner = get_setting("payment_owner")
    card = get_setting("payment_card")
    if not bank or not owner or not card:
        return (
            "⚠️ اطلاعات پرداخت هنوز توسط ادمین کامل نشده است.\n"
            "لطفاً کمی بعد دوباره تلاش کن یا با پشتیبانی در ارتباط باش."
        )
    return (
        "💳 <b>کارت به کارت</b>\n\n"
        f"لطفاً مبلغ <b>{fmt_price(amount)}</b> تومان را به اطلاعات زیر واریز کنید:\n\n"
        f"🏦 {html.escape(bank)}\n"
        f"👤 {html.escape(owner)}\n"
        f"💳 شماره کارت <code>{html.escape(card)}</code>\n\n"
        "📸 پس از واریز، لطفاً تصویر رسید یا شماره پیگیری خود را ارسال کنید.\n"
        "برای لغو هم می‌توانید واژه <b>لغو</b> را بفرستید."
    )


def purchase_admin_text(purchase_like, method_title: str) -> str:
    return (
        f"❗️|💳 خرید جدید ( {method_title} )\n\n"
        f"▫️آیدی کاربر: <code>{purchase_like['user_id']}</code>\n"
        f"👨‍💼اسم کاربر: {html.escape(purchase_like['full_name'] or 'ㅤ')}\n"
        f"⚡️ نام کاربری: {html.escape(display_username(purchase_like['username']))}\n"
        f"💰مبلغ پرداختی: {fmt_price(purchase_like['amount'])} تومان\n"
        f"🚦سرور: {html.escape(purchase_like['type_name'])}\n"
        f"✏️ نام سرویس: {html.escape(purchase_like['service_name'])}\n"
        f"🔋حجم سرویس: {purchase_like['volume_gb']} گیگ\n"
        f"⏰ مدت سرویس: {purchase_like['duration_days']} روز"
    )


def wallet_admin_text(pay) -> str:
    return (
        "💰 درخواست جدید شارژ کیف پول\n\n"
        f"▫️آیدی کاربر: <code>{pay['user_id']}</code>\n"
        f"👨‍💼اسم کاربر: {html.escape(pay['full_name'] or 'ㅤ')}\n"
        f"⚡️ نام کاربری: {html.escape(display_username(pay['username']))}\n"
        f"💳 روش پرداخت: کارت به کارت\n"
        f"💰 مبلغ شارژ: {fmt_price(pay['amount'])} تومان"
    )


def user_joined_admin_text(tg_user) -> str:
    return (
        "📢 | یه گل جدید عضو ربات شد :\n\n"
        f"نام و نام خانوادگی: {html.escape(display_name(tg_user))}\n"
        f"نام کاربری: {html.escape(display_username(tg_user.username))}\n"
        f"آیدی عددی: <code>{tg_user.id}</code>"
    )


def config_caption(purchase) -> str:
    link = (purchase["inquiry_link"] or "").strip()
    volume_web = (
        f'<a href="{html.escape(link)}">مشاهده استعلام حجم</a>' if link else "ثبت نشده"
    )
    return (
        f"🔮 نام سرویس: {html.escape(purchase['service_name'])}\n"
        f"🔋حجم سرویس: {purchase['volume_gb']} گیگ\n"
        f"⏰ مدت سرویس: {purchase['duration_days']} روز\n\n"
        f"🔋 Volume web: {volume_web}\n\n"
        "🌟 QRCode سرویس شما آماده است."
    )


def config_text_body(purchase) -> str:
    return (
        "💝 <b>config :</b>\n"
        f"<code>{html.escape(purchase['config_text'])}</code>"
    )


# ---------------------------
# Markups
# ---------------------------
def main_menu_markup(user_id: int):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("خرید کانفیگ جدید"), types.KeyboardButton("کانفیگ های من"))
    kb.add(types.KeyboardButton("حساب کاربری"), types.KeyboardButton("ارتباط با پشتیبانی"))
    if is_admin(user_id):
        kb.add(types.KeyboardButton("پنل مدیریت"))
    return kb


def admin_menu_markup():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("مدیریت نوع ها"), types.KeyboardButton("مدیریت پکیج ها"))
    kb.add(types.KeyboardButton("ثبت کانفیگ"), types.KeyboardButton("کانفیگ های ثبت شده"))
    kb.add(types.KeyboardButton("ویرایش اطلاعات"), types.KeyboardButton("بازگشت به منوی اصلی"))
    return kb


def support_markup():
    url = safe_support_url(get_setting("support_username"))
    if not url:
        return None
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💬 ورود به پشتیبانی", url=url))
    return kb


def profile_markup():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ شارژ کیف پول", callback_data="profile_charge_wallet"))
    return kb


def payment_method_markup(package_id: int):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💰 پرداخت از موجودی", callback_data=f"pay_wallet_{package_id}"))
    kb.add(types.InlineKeyboardButton("💳 کارت به کارت", callback_data=f"pay_card_{package_id}"))
    return kb


def renew_markup():
    url = safe_support_url(get_setting("support_username"))
    if not url:
        return None
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تمدید سرویس", url=url))
    return kb


def payment_review_markup(payment_id: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ تایید", callback_data=f"adm_pay_approve_{payment_id}"),
        types.InlineKeyboardButton("❌ رد", callback_data=f"adm_pay_reject_{payment_id}"),
    )
    return kb


def noop_button(text: str):
    return types.InlineKeyboardButton(text, callback_data="noop")


# ---------------------------
# Send helpers
# ---------------------------
def send_profile(chat_id: int, user_id: int):
    user_row = get_user(user_id)
    if not user_row:
        return
    bot.send_message(chat_id, profile_text(user_row), reply_markup=profile_markup())


def send_support(chat_id: int):
    markup = support_markup()
    if not markup:
        bot.send_message(chat_id, "⚠️ پشتیبانی هنوز ست نشده است.")
        return
    bot.send_message(chat_id, "💬 برای ارتباط با پشتیبانی، روی دکمه زیر بزنید.", reply_markup=markup)


def send_type_selection(chat_id: int):
    type_rows = get_types()
    if not type_rows:
        bot.send_message(chat_id, "⚠️ هنوز نوعی برای فروش ثبت نشده است.")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in type_rows:
        kb.add(types.InlineKeyboardButton(f"🚦 {row['name']}", callback_data=f"buy_type_{row['id']}"))
    bot.send_message(chat_id, "🌈 نوع کانفیگ موردنظر را انتخاب کن:", reply_markup=kb)


def send_packages_for_type(chat_id: int, type_id: int):
    packages = get_packages(type_id)
    if not packages:
        bot.send_message(chat_id, "⚠️ برای این نوع هنوز پکیجی ثبت نشده است.")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pkg in packages:
        text = (
            f"📦 {pkg['name']} | {pkg['volume_gb']} گیگ | {pkg['duration_days']} روز | "
            f"{fmt_price(pkg['price'])} تومان"
        )
        kb.add(types.InlineKeyboardButton(text, callback_data=f"buy_pkg_{pkg['id']}"))
    bot.send_message(chat_id, "🧾 یکی از پکیج‌های زیر را انتخاب کن:", reply_markup=kb)


def send_my_configs(chat_id: int, user_id: int):
    purchases = get_user_purchases(user_id)
    if not purchases:
        bot.send_message(chat_id, "📭 هنوز سرویسی برای شما ثبت نشده است.")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for item in purchases:
        kb.add(types.InlineKeyboardButton(f"🔮 {item['service_name']}", callback_data=f"my_cfg_{item['id']}"))
    bot.send_message(chat_id, "📦 سرویس‌های شما به شرح زیر است:", reply_markup=kb)


def make_qr_image(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    bio.name = "config_qr.png"
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


def send_config_to_user(chat_id: int, purchase_id: int):
    purchase = get_purchase(purchase_id)
    if not purchase:
        bot.send_message(chat_id, "⚠️ اطلاعات سرویس پیدا نشد.")
        return

    qr_file = make_qr_image(purchase["config_text"])
    bot.send_photo(
        chat_id,
        qr_file,
        caption=config_caption(purchase),
        reply_markup=renew_markup(),
    )
    bot.send_message(chat_id, config_text_body(purchase))


def notify_admins_new_user(tg_user):
    text = user_joined_admin_text(tg_user)
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text)
        except Exception:
            pass


def notify_admins_purchase_done(purchase_id: int):
    purchase = get_purchase(purchase_id)
    if not purchase:
        return
    method = "کیف پول" if purchase["payment_method"] == "wallet" else "کارت به کارت"
    text = purchase_admin_text(purchase, method)
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text)
        except Exception:
            pass


def notify_admins_wallet_charge_request(payment_id: int):
    pay = get_payment(payment_id)
    if not pay:
        return
    text = wallet_admin_text(pay)
    receipt_file_id = pay["receipt_file_id"]
    receipt_text = (pay["receipt_text"] or "").strip()
    footer = f"\n\n🧾 وضعیت: در انتظار بررسی ادمین"
    if receipt_text:
        footer += f"\n✍️ متن/شماره پیگیری: {html.escape(receipt_text)}"
    for admin_id in ADMIN_IDS:
        try:
            if receipt_file_id:
                bot.send_photo(
                    admin_id,
                    receipt_file_id,
                    caption=text + footer,
                    reply_markup=payment_review_markup(payment_id),
                )
            else:
                bot.send_message(
                    admin_id,
                    text + footer,
                    reply_markup=payment_review_markup(payment_id),
                )
        except Exception:
            pass


def notify_admins_purchase_request(payment_id: int):
    pay = get_payment(payment_id)
    if not pay:
        return
    text = purchase_admin_text(pay, "کارت به کارت")
    receipt_file_id = pay["receipt_file_id"]
    receipt_text = (pay["receipt_text"] or "").strip()
    footer = f"\n\n🧾 وضعیت: در انتظار تایید رسید"
    if receipt_text:
        footer += f"\n✍️ متن/شماره پیگیری: {html.escape(receipt_text)}"
    for admin_id in ADMIN_IDS:
        try:
            if receipt_file_id:
                bot.send_photo(
                    admin_id,
                    receipt_file_id,
                    caption=text + footer,
                    reply_markup=payment_review_markup(payment_id),
                )
            else:
                bot.send_message(
                    admin_id,
                    text + footer,
                    reply_markup=payment_review_markup(payment_id),
                )
        except Exception:
            pass


def send_manage_types(chat_id: int):
    rows = get_types()
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(types.InlineKeyboardButton("➕ اضافه کردن نوع جدید", callback_data="adm_type_add"))
    for row in rows:
        kb.row(
            noop_button(f"📌 {row['name']}"),
            types.InlineKeyboardButton("✏️", callback_data=f"adm_type_edit_{row['id']}"),
            types.InlineKeyboardButton("🗑", callback_data=f"adm_type_del_{row['id']}"),
        )
    text = "🛠 <b>مدیریت نوع‌ها</b>\n\nاز دکمه‌های زیر برای افزودن، ویرایش یا حذف نوع‌ها استفاده کنید."
    if not rows:
        text += "\n\nهنوز نوعی ثبت نشده است."
    bot.send_message(chat_id, text, reply_markup=kb)


def send_manage_packages(chat_id: int):
    rows = get_packages()
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(types.InlineKeyboardButton("➕ اضافه کردن پکیج جدید", callback_data="adm_pkg_add"))
    for row in rows:
        label = (
            f"📦 {row['type_name']} | {row['name']} | {row['volume_gb']}GB | {row['duration_days']}D | {fmt_price(row['price'])}"
        )
        kb.row(
            noop_button(label),
            types.InlineKeyboardButton("✏️", callback_data=f"adm_pkg_edit_{row['id']}"),
            types.InlineKeyboardButton("🗑", callback_data=f"adm_pkg_del_{row['id']}"),
        )
    text = "🗂 <b>مدیریت پکیج‌ها</b>\n\nپکیج‌های فروش از این بخش مدیریت می‌شوند."
    if not rows:
        text += "\n\nهنوز پکیجی ثبت نشده است."
    bot.send_message(chat_id, text, reply_markup=kb)


def send_settings_menu(chat_id: int):
    support_value = get_setting("support_username") or "ثبت نشده"
    card_value = get_setting("payment_card") or "ثبت نشده"
    bank_value = get_setting("payment_bank") or "ثبت نشده"
    owner_value = get_setting("payment_owner") or "ثبت نشده"

    text = (
        "⚙️ <b>ویرایش اطلاعات</b>\n\n"
        f"🆔 آیدی پشتیبانی: {html.escape(support_value)}\n"
        f"💳 شماره کارت: <code>{html.escape(card_value)}</code>\n"
        f"🏦 بانک: {html.escape(bank_value)}\n"
        f"👤 نام دارنده کارت: {html.escape(owner_value)}"
    )
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🆔 ویرایش آیدی پشتیبانی", callback_data="adm_set_support"))
    kb.add(types.InlineKeyboardButton("💳 ویرایش اطلاعات پرداخت", callback_data="adm_payment_info"))
    bot.send_message(chat_id, text, reply_markup=kb)


def send_payment_info_menu(chat_id: int):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("💳 ویرایش شماره کارت", callback_data="adm_set_card"))
    kb.add(types.InlineKeyboardButton("🏦 ویرایش بانک", callback_data="adm_set_bank"))
    kb.add(types.InlineKeyboardButton("👤 ویرایش نام و نام خانوادگی", callback_data="adm_set_owner"))
    bot.send_message(chat_id, "💳 یکی از بخش‌های اطلاعات پرداخت را انتخاب کنید:", reply_markup=kb)


def send_add_config_type_selector(chat_id: int):
    rows = get_types()
    if not rows:
        bot.send_message(chat_id, "⚠️ ابتدا باید حداقل یک نوع ایجاد کنید.")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        kb.add(types.InlineKeyboardButton(f"🚦 {row['name']}", callback_data=f"adm_cfg_type_{row['id']}"))
    bot.send_message(chat_id, "🧩 نوع کانفیگ را انتخاب کنید:", reply_markup=kb)


def send_stock_overview(chat_id: int):
    rows = get_remaining_stock_packages()
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        text = f"{row['type_name']} - {row['volume_gb']} گیگ | باقی‌مانده: {row['remaining_count']}"
        kb.add(types.InlineKeyboardButton(text, callback_data=f"adm_stock_pkg_{row['id']}"))
    if rows:
        bot.send_message(chat_id, "📦 <b>کانفیگ‌های ثبت شده</b>\n\nبرای مشاهده موجودی هر گروه روی آن بزنید.", reply_markup=kb)
    else:
        bot.send_message(chat_id, "📭 هنوز کانفیگی ثبت نشده است.")


def send_stock_items(chat_id: int, package_id: int):
    rows = get_remaining_configs_by_package(package_id)
    if not rows:
        bot.send_message(chat_id, "📭 برای این پکیج کانفیگ آزاد باقی نمانده است.")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        kb.add(types.InlineKeyboardButton(f"🔮 {row['service_name']}", callback_data=f"adm_stock_cfg_{row['id']}"))
    bot.send_message(chat_id, "📋 لیست کانفیگ‌های باقی‌مانده:", reply_markup=kb)


def send_admin_config_detail(chat_id: int, config_id: int):
    row = get_config(config_id)
    if not row:
        bot.send_message(chat_id, "⚠️ این کانفیگ پیدا نشد.")
        return
    text = (
        f"🔮 نام سرویس: {html.escape(row['service_name'])}\n"
        f"🚦 نوع: {html.escape(row['type_name'])}\n"
        f"📦 پکیج: {html.escape(row['package_name'])}\n"
        f"🔋 حجم: {row['volume_gb']} گیگ\n"
        f"⏰ مدت: {row['duration_days']} روز\n\n"
        f"💝 config :\n<code>{html.escape(row['config_text'])}</code>\n\n"
        f"🔋 Volume web:\n{html.escape(row['inquiry_link'] or 'ثبت نشده')}"
    )
    bot.send_message(chat_id, text)


# ---------------------------
# Admin decision helpers
# ---------------------------
def finalize_admin_payment_decision(admin_id: int, payment_id: int, decision: str, note: str):
    note = "" if note.strip() in {"-", ".", "ندارد", "بدون متن"} else note.strip()
    pay = get_payment(payment_id)
    if not pay:
        bot.send_message(admin_id, "⚠️ این درخواست پیدا نشد.")
        return

    if pay["kind"] == "wallet":
        if decision == "approve":
            approved_pay, err = approve_wallet_charge(payment_id, note)
            if err:
                bot.send_message(admin_id, f"⚠️ {err}")
                return
            bot.send_message(admin_id, "✅ درخواست شارژ کیف پول تایید شد.")
            msg = "✅ واریزی شما تایید شد."
            if note:
                msg += f"\n\n✍️ پیام ادمین:\n{note}"
            user = get_user(approved_pay["user_id"])
            msg += f"\n\n💰 موجودی جدید شما: {fmt_price(user['balance'])} تومان"
            bot.send_message(approved_pay["user_id"], msg)
        else:
            rejected_pay, err = reject_wallet_charge(payment_id, note)
            if err:
                bot.send_message(admin_id, f"⚠️ {err}")
                return
            bot.send_message(admin_id, "❌ درخواست شارژ کیف پول رد شد.")
            msg = "❌ رسید شما رد شد."
            if note:
                msg += f"\n\n✍️ پیام ادمین:\n{note}"
            bot.send_message(rejected_pay["user_id"], msg)
        return

    if pay["kind"] == "purchase":
        if decision == "approve":
            approved_pay, purchase, err = approve_purchase_payment(payment_id, note)
            if err:
                bot.send_message(admin_id, f"⚠️ {err}")
                return
            bot.send_message(admin_id, "✅ خرید تایید شد و سرویس تحویل کاربر شد.")
            user_msg = "✅ پرداخت شما تایید شد."
            if note:
                user_msg += f"\n\n✍️ پیام ادمین:\n{note}"
            bot.send_message(approved_pay["user_id"], user_msg)
            send_config_to_user(approved_pay["user_id"], purchase["id"])
            notify_admins_purchase_done(purchase["id"])
        else:
            rejected_pay, err = reject_purchase_payment(payment_id, note)
            if err:
                bot.send_message(admin_id, f"⚠️ {err}")
                return
            bot.send_message(admin_id, "❌ خرید رد شد و رزرو کانفیگ آزاد شد.")
            user_msg = "❌ رسید شما رد شد."
            if note:
                user_msg += f"\n\n✍️ پیام ادمین:\n{note}"
            bot.send_message(rejected_pay["user_id"], user_msg)


# ---------------------------
# Start / general commands
# ---------------------------
@bot.message_handler(commands=["start"])
def handle_start(message):
    upsert_user(message.from_user)
    state_clear(message.from_user.id)
    bot.send_message(
        message.chat.id,
        start_text(display_name(message.from_user)),
        reply_markup=main_menu_markup(message.from_user.id),
    )
    notify_admins_new_user(message.from_user)


# ---------------------------
# Callback queries
# ---------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    user_id = call.from_user.id
    data = call.data or ""
    upsert_user(call.from_user)

    if data == "noop":
        return

    # User menu
    if data == "profile_charge_wallet":
        state_set(user_id, "wallet_amount")
        bot.send_message(call.message.chat.id, "💰 لطفاً مبلغ موردنظر را به تومان وارد کنید.\nمثال: <code>500000</code>\n\nبرای لغو، واژه <b>لغو</b> را بفرستید.")
        return

    if data.startswith("buy_type_"):
        type_id = int(data.split("_")[-1])
        send_packages_for_type(call.message.chat.id, type_id)
        return

    if data.startswith("buy_pkg_"):
        package_id = int(data.split("_")[-1])
        pkg = get_package(package_id)
        if not pkg:
            bot.send_message(call.message.chat.id, "⚠️ این پکیج پیدا نشد.")
            return
        bot.send_message(call.message.chat.id, package_summary_text(pkg), reply_markup=payment_method_markup(package_id))
        return

    if data.startswith("pay_wallet_"):
        package_id = int(data.split("_")[-1])
        purchase, err = create_wallet_purchase(user_id, package_id)
        if err:
            bot.send_message(call.message.chat.id, f"⚠️ {err}")
            return
        bot.send_message(call.message.chat.id, "✅ خرید شما با موفقیت از کیف پول انجام شد.")
        send_config_to_user(call.message.chat.id, purchase["id"])
        notify_admins_purchase_done(purchase["id"])
        return

    if data.startswith("pay_card_"):
        package_id = int(data.split("_")[-1])
        payment, err = create_purchase_payment_with_reserve(user_id, package_id)
        if err:
            bot.send_message(call.message.chat.id, f"⚠️ {err}")
            return
        text = payment_card_text(payment["amount"])
        if text.startswith("⚠️ اطلاعات پرداخت"):
            reject_purchase_payment(payment["id"], "اطلاعات پرداخت هنوز توسط ادمین تنظیم نشده بود.")
            bot.send_message(call.message.chat.id, text)
            return
        state_set(user_id, "await_receipt", payment_id=payment["id"], kind="purchase")
        bot.send_message(call.message.chat.id, text)
        return

    if data.startswith("my_cfg_"):
        purchase_id = int(data.split("_")[-1])
        purchase = get_purchase(purchase_id)
        if not purchase or purchase["user_id"] != user_id:
            bot.send_message(call.message.chat.id, "⚠️ این سرویس در دسترس نیست.")
            return
        send_config_to_user(call.message.chat.id, purchase_id)
        return

    if data == "wallet_method_card":
        state = state_get(user_id)
        if not state or state["name"] != "wallet_method":
            bot.send_message(call.message.chat.id, "⚠️ لطفاً دوباره مبلغ را وارد کنید.")
            return
        amount = state["data"]["amount"]
        payment = create_wallet_charge_payment(user_id, amount)
        text = payment_card_text(amount)
        if text.startswith("⚠️ اطلاعات پرداخت"):
            reject_wallet_charge(payment["id"], "اطلاعات پرداخت هنوز توسط ادمین تنظیم نشده بود.")
            state_clear(user_id)
            bot.send_message(call.message.chat.id, text)
            return
        state_set(user_id, "await_receipt", payment_id=payment["id"], kind="wallet")
        bot.send_message(call.message.chat.id, text)
        return

    # Admin area
    if not is_admin(user_id):
        return

    if data == "adm_type_add":
        state_set(user_id, "admin_add_type")
        bot.send_message(call.message.chat.id, "✍️ نام نوع جدید را ارسال کنید.\nبرای لغو، واژه <b>لغو</b> را بفرستید.")
        return

    if data.startswith("adm_type_edit_"):
        type_id = int(data.split("_")[-1])
        row = get_type(type_id)
        if not row:
            bot.send_message(call.message.chat.id, "⚠️ این نوع پیدا نشد.")
            return
        state_set(user_id, "admin_edit_type", type_id=type_id)
        bot.send_message(call.message.chat.id, f"✏️ نام جدید برای نوع <b>{html.escape(row['name'])}</b> را ارسال کنید.")
        return

    if data.startswith("adm_type_del_"):
        type_id = int(data.split("_")[-1])
        row = get_type(type_id)
        if not row:
            bot.send_message(call.message.chat.id, "⚠️ این نوع پیدا نشد.")
            return
        if not can_delete_type(type_id):
            bot.send_message(call.message.chat.id, "⚠️ این نوع دارای پکیج است و فعلاً قابل حذف نیست. ابتدا پکیج‌های مربوطه را حذف کنید.")
            return
        delete_type(type_id)
        bot.send_message(call.message.chat.id, "🗑 نوع موردنظر حذف شد.")
        send_manage_types(call.message.chat.id)
        return

    if data == "adm_pkg_add":
        rows = get_types()
        if not rows:
            bot.send_message(call.message.chat.id, "⚠️ ابتدا یک نوع بسازید.")
            return
        kb = types.InlineKeyboardMarkup(row_width=1)
        for row in rows:
            kb.add(types.InlineKeyboardButton(f"🚦 {row['name']}", callback_data=f"adm_pkg_type_{row['id']}"))
        bot.send_message(call.message.chat.id, "🧩 نوع این پکیج را انتخاب کنید:", reply_markup=kb)
        return

    if data.startswith("adm_pkg_type_"):
        type_id = int(data.split("_")[-1])
        state_set(user_id, "admin_add_pkg_name", type_id=type_id)
        bot.send_message(call.message.chat.id, "✍️ نام پکیج را ارسال کنید.")
        return

    if data.startswith("adm_pkg_edit_"):
        package_id = int(data.split("_")[-1])
        row = get_package(package_id)
        if not row:
            bot.send_message(call.message.chat.id, "⚠️ این پکیج پیدا نشد.")
            return
        state_set(user_id, "admin_edit_pkg_name", package_id=package_id, type_id=row["type_id"])
        bot.send_message(call.message.chat.id, f"✏️ نام جدید برای پکیج <b>{html.escape(row['name'])}</b> را ارسال کنید.")
        return

    if data.startswith("adm_pkg_del_"):
        package_id = int(data.split("_")[-1])
        if not can_delete_package(package_id):
            bot.send_message(call.message.chat.id, "⚠️ این پکیج دارای کانفیگ ثبت‌شده یا سابقه فروش است و قابل حذف نیست.")
            return
        delete_package(package_id)
        bot.send_message(call.message.chat.id, "🗑 پکیج موردنظر حذف شد.")
        send_manage_packages(call.message.chat.id)
        return

    if data == "adm_set_support":
        state_set(user_id, "admin_set_support")
        bot.send_message(call.message.chat.id, "🆔 آیدی پشتیبانی را ارسال کنید.\nنمونه: <code>@Tracklessvpnadmin</code>")
        return

    if data == "adm_payment_info":
        send_payment_info_menu(call.message.chat.id)
        return

    if data == "adm_set_card":
        state_set(user_id, "admin_set_card")
        bot.send_message(call.message.chat.id, "💳 شماره کارت را بدون فاصله یا با فاصله ارسال کنید.")
        return

    if data == "adm_set_bank":
        state_set(user_id, "admin_set_bank")
        bot.send_message(call.message.chat.id, "🏦 نام بانک را ارسال کنید.")
        return

    if data == "adm_set_owner":
        state_set(user_id, "admin_set_owner")
        bot.send_message(call.message.chat.id, "👤 نام و نام خانوادگی دارنده کارت را ارسال کنید.")
        return

    if data.startswith("adm_cfg_type_"):
        type_id = int(data.split("_")[-1])
        packages = get_packages(type_id)
        if not packages:
            bot.send_message(call.message.chat.id, "⚠️ برای این نوع، پکیجی ثبت نشده است.")
            return
        kb = types.InlineKeyboardMarkup(row_width=1)
        for pkg in packages:
            text = f"📦 {pkg['name']} | {pkg['volume_gb']} گیگ | {pkg['duration_days']} روز"
            kb.add(types.InlineKeyboardButton(text, callback_data=f"adm_cfg_pkg_{pkg['id']}"))
        bot.send_message(call.message.chat.id, "📦 پکیج مربوط را انتخاب کنید:", reply_markup=kb)
        return

    if data.startswith("adm_cfg_pkg_"):
        package_id = int(data.split("_")[-1])
        pkg = get_package(package_id)
        if not pkg:
            bot.send_message(call.message.chat.id, "⚠️ پکیج پیدا نشد.")
            return
        state_set(user_id, "admin_add_cfg_service_name", type_id=pkg["type_id"], package_id=package_id)
        bot.send_message(call.message.chat.id, "🔮 نام سرویس را ارسال کنید.")
        return

    if data.startswith("adm_stock_pkg_"):
        package_id = int(data.split("_")[-1])
        send_stock_items(call.message.chat.id, package_id)
        return

    if data.startswith("adm_stock_cfg_"):
        config_id = int(data.split("_")[-1])
        send_admin_config_detail(call.message.chat.id, config_id)
        return

    if data.startswith("adm_pay_approve_"):
        payment_id = int(data.split("_")[-1])
        state_set(user_id, "admin_payment_note", payment_id=payment_id, decision="approve")
        bot.send_message(call.message.chat.id, "✍️ متن پاسخ ادمین را ارسال کنید.\nبرای بدون متن، فقط <b>-</b> یا <b>.</b> بفرستید.")
        return

    if data.startswith("adm_pay_reject_"):
        payment_id = int(data.split("_")[-1])
        state_set(user_id, "admin_payment_note", payment_id=payment_id, decision="reject")
        bot.send_message(call.message.chat.id, "✍️ متن دلیل رد را ارسال کنید.\nبرای بدون متن، فقط <b>-</b> یا <b>.</b> بفرستید.")
        return


# ---------------------------
# Photos (receipts)
# ---------------------------
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    upsert_user(message.from_user)
    user_id = message.from_user.id
    state = state_get(user_id)

    if not state:
        bot.send_message(message.chat.id, "📸 تصویر شما دریافت شد، اما در حال حاضر منتظر رسیدی از طرف شما نبودم.")
        return

    if state["name"] == "await_receipt":
        payment_id = state["data"]["payment_id"]
        kind = state["data"]["kind"]
        file_id = message.photo[-1].file_id
        receipt_text = message.caption or ""
        update_payment_receipt(payment_id, file_id=file_id, receipt_text=receipt_text)
        state_clear(user_id)
        bot.send_message(message.chat.id, "✅ رسید شما دریافت شد و برای بررسی به ادمین ارسال گردید.")
        if kind == "wallet":
            notify_admins_wallet_charge_request(payment_id)
        else:
            notify_admins_purchase_request(payment_id)
        return

    bot.send_message(message.chat.id, "⚠️ فعلاً نیازی به ارسال عکس در این مرحله نیست.")


# ---------------------------
# Text messages
# ---------------------------
@bot.message_handler(content_types=["text"])
def handle_text(message):
    upsert_user(message.from_user)
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if text == "لغو":
        state_clear(user_id)
        if is_admin(user_id):
            bot.send_message(message.chat.id, "🟡 عملیات لغو شد.", reply_markup=admin_menu_markup())
        else:
            bot.send_message(message.chat.id, "🟡 عملیات لغو شد.", reply_markup=main_menu_markup(user_id))
        return

    state = state_get(user_id)
    if state:
        state_name = state["name"]
        data = state["data"]

        # User states
        if state_name == "wallet_amount":
            amount = parse_int(text)
            if not amount or amount <= 0:
                bot.send_message(message.chat.id, "⚠️ لطفاً مبلغ صحیح را فقط به تومان وارد کنید.")
                return
            state_set(user_id, "wallet_method", amount=amount)
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💳 کارت به کارت", callback_data="wallet_method_card"))
            bot.send_message(message.chat.id, f"💰 مبلغ <b>{fmt_price(amount)}</b> تومان ثبت شد.\nلطفاً روش شارژ کیف پول را انتخاب کنید:", reply_markup=kb)
            return

        if state_name == "await_receipt":
            payment_id = data["payment_id"]
            kind = data["kind"]
            update_payment_receipt(payment_id, file_id=None, receipt_text=text)
            state_clear(user_id)
            bot.send_message(message.chat.id, "✅ رسید/شماره پیگیری شما دریافت شد و برای بررسی به ادمین ارسال گردید.")
            if kind == "wallet":
                notify_admins_wallet_charge_request(payment_id)
            else:
                notify_admins_purchase_request(payment_id)
            return

        # Admin states
        if is_admin(user_id):
            if state_name == "admin_add_type":
                try:
                    add_type(text)
                    bot.send_message(message.chat.id, "✅ نوع جدید با موفقیت ثبت شد.")
                except sqlite3.IntegrityError:
                    bot.send_message(message.chat.id, "⚠️ این نام قبلاً ثبت شده است.")
                    return
                state_clear(user_id)
                send_manage_types(message.chat.id)
                return

            if state_name == "admin_edit_type":
                try:
                    update_type(data["type_id"], text)
                    bot.send_message(message.chat.id, "✅ نام نوع با موفقیت ویرایش شد.")
                except sqlite3.IntegrityError:
                    bot.send_message(message.chat.id, "⚠️ این نام قبلاً استفاده شده است.")
                    return
                state_clear(user_id)
                send_manage_types(message.chat.id)
                return

            if state_name == "admin_add_pkg_name":
                state_set(user_id, "admin_add_pkg_volume", type_id=data["type_id"], name=text)
                bot.send_message(message.chat.id, "🔋 حجم پکیج را به گیگ وارد کنید.\nمثال: <code>30</code>")
                return

            if state_name == "admin_add_pkg_volume":
                volume = parse_int(text)
                if not volume or volume <= 0:
                    bot.send_message(message.chat.id, "⚠️ حجم معتبر وارد کنید.")
                    return
                state_set(user_id, "admin_add_pkg_duration", type_id=data["type_id"], name=data["name"], volume=volume)
                bot.send_message(message.chat.id, "⏰ مدت پکیج را به روز وارد کنید.\nمثال: <code>45</code>")
                return

            if state_name == "admin_add_pkg_duration":
                duration = parse_int(text)
                if not duration or duration <= 0:
                    bot.send_message(message.chat.id, "⚠️ مدت معتبر وارد کنید.")
                    return
                state_set(user_id, "admin_add_pkg_price", type_id=data["type_id"], name=data["name"], volume=data["volume"], duration=duration)
                bot.send_message(message.chat.id, "💳 قیمت پکیج را به تومان وارد کنید.\nمثال: <code>90000</code>")
                return

            if state_name == "admin_add_pkg_price":
                price = parse_int(text)
                if not price or price <= 0:
                    bot.send_message(message.chat.id, "⚠️ قیمت معتبر وارد کنید.")
                    return
                add_package(data["type_id"], data["name"], data["volume"], data["duration"], price)
                state_clear(user_id)
                bot.send_message(message.chat.id, "✅ پکیج جدید با موفقیت ثبت شد.")
                send_manage_packages(message.chat.id)
                return

            if state_name == "admin_edit_pkg_name":
                state_set(user_id, "admin_edit_pkg_volume", package_id=data["package_id"], type_id=data["type_id"], name=text)
                bot.send_message(message.chat.id, "🔋 حجم جدید پکیج را به گیگ وارد کنید.")
                return

            if state_name == "admin_edit_pkg_volume":
                volume = parse_int(text)
                if not volume or volume <= 0:
                    bot.send_message(message.chat.id, "⚠️ حجم معتبر وارد کنید.")
                    return
                state_set(user_id, "admin_edit_pkg_duration", package_id=data["package_id"], type_id=data["type_id"], name=data["name"], volume=volume)
                bot.send_message(message.chat.id, "⏰ مدت جدید پکیج را به روز وارد کنید.")
                return

            if state_name == "admin_edit_pkg_duration":
                duration = parse_int(text)
                if not duration or duration <= 0:
                    bot.send_message(message.chat.id, "⚠️ مدت معتبر وارد کنید.")
                    return
                state_set(user_id, "admin_edit_pkg_price", package_id=data["package_id"], type_id=data["type_id"], name=data["name"], volume=data["volume"], duration=duration)
                bot.send_message(message.chat.id, "💳 قیمت جدید پکیج را به تومان وارد کنید.")
                return

            if state_name == "admin_edit_pkg_price":
                price = parse_int(text)
                if not price or price <= 0:
                    bot.send_message(message.chat.id, "⚠️ قیمت معتبر وارد کنید.")
                    return
                update_package(data["package_id"], data["name"], data["volume"], data["duration"], price)
                state_clear(user_id)
                bot.send_message(message.chat.id, "✅ اطلاعات پکیج با موفقیت به‌روزرسانی شد.")
                send_manage_packages(message.chat.id)
                return

            if state_name == "admin_set_support":
                set_setting("support_username", text)
                state_clear(user_id)
                bot.send_message(message.chat.id, "✅ آیدی پشتیبانی ذخیره شد.")
                send_settings_menu(message.chat.id)
                return

            if state_name == "admin_set_card":
                card_number = normalize_text_number(text)
                if not re.fullmatch(r"\d{16}", card_number):
                    bot.send_message(message.chat.id, "⚠️ شماره کارت باید 16 رقمی باشد.")
                    return
                set_setting("payment_card", card_number)
                state_clear(user_id)
                bot.send_message(message.chat.id, "✅ شماره کارت ذخیره شد.")
                send_payment_info_menu(message.chat.id)
                return

            if state_name == "admin_set_bank":
                set_setting("payment_bank", text)
                state_clear(user_id)
                bot.send_message(message.chat.id, "✅ نام بانک ذخیره شد.")
                send_payment_info_menu(message.chat.id)
                return

            if state_name == "admin_set_owner":
                set_setting("payment_owner", text)
                state_clear(user_id)
                bot.send_message(message.chat.id, "✅ نام و نام خانوادگی دارنده کارت ذخیره شد.")
                send_payment_info_menu(message.chat.id)
                return

            if state_name == "admin_add_cfg_service_name":
                state_set(user_id, "admin_add_cfg_text", type_id=data["type_id"], package_id=data["package_id"], service_name=text)
                bot.send_message(message.chat.id, "💝 متن کامل کانفیگ را ارسال کنید.")
                return

            if state_name == "admin_add_cfg_text":
                state_set(user_id, "admin_add_cfg_link", type_id=data["type_id"], package_id=data["package_id"], service_name=data["service_name"], config_text=text)
                bot.send_message(message.chat.id, "🔋 لینک استعلام/Volume web را ارسال کنید.\nاگر ندارید، فقط یک خط تیره <b>-</b> بفرستید.")
                return

            if state_name == "admin_add_cfg_link":
                inquiry_link = "" if text.strip() in {"-", ".", "ندارد"} else text.strip()
                add_config(data["type_id"], data["package_id"], data["service_name"], data["config_text"], inquiry_link)
                state_clear(user_id)
                bot.send_message(message.chat.id, "✅ کانفیگ با موفقیت ثبت شد.\nبرای افزودن مورد بعدی دوباره از گزینه <b>ثبت کانفیگ</b> استفاده کنید.")
                return

            if state_name == "admin_payment_note":
                finalize_admin_payment_decision(user_id, data["payment_id"], data["decision"], text)
                state_clear(user_id)
                return

    # Main menu routing
    if text == "خرید کانفیگ جدید":
        send_type_selection(message.chat.id)
        return

    if text == "کانفیگ های من":
        send_my_configs(message.chat.id, user_id)
        return

    if text == "حساب کاربری":
        send_profile(message.chat.id, user_id)
        return

    if text == "ارتباط با پشتیبانی":
        send_support(message.chat.id)
        return

    if text == "پنل مدیریت" and is_admin(user_id):
        bot.send_message(message.chat.id, "👑 به پنل مدیریت خوش آمدید.", reply_markup=admin_menu_markup())
        return

    if text == "بازگشت به منوی اصلی" and is_admin(user_id):
        bot.send_message(message.chat.id, "🏠 به منوی اصلی برگشتید.", reply_markup=main_menu_markup(user_id))
        return

    if is_admin(user_id):
        if text == "مدیریت نوع ها":
            send_manage_types(message.chat.id)
            return
        if text == "مدیریت پکیج ها":
            send_manage_packages(message.chat.id)
            return
        if text == "ویرایش اطلاعات":
            send_settings_menu(message.chat.id)
            return
        if text == "ثبت کانفیگ":
            send_add_config_type_selector(message.chat.id)
            return
        if text == "کانفیگ های ثبت شده":
            send_stock_overview(message.chat.id)
            return

    bot.send_message(
        message.chat.id,
        "🌷 پیام شما دریافت شد؛ لطفاً از دکمه‌های منو استفاده کنید.",
        reply_markup=main_menu_markup(user_id) if not is_admin(user_id) else admin_menu_markup(),
    )


# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    init_db()
    print("TracklessVPN bot is running...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
