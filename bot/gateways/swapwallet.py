# -*- coding: utf-8 -*-
"""
SwapWallet Resid (Receipt) payment gateway — IRT-based invoice via v1 API.
"""
import json
import urllib.request
import urllib.parse
import urllib.error

from ..config import SWAPWALLET_BASE_URL
from ..db import setting_get
from ..helpers import fmt_price, esc
from ..bot_instance import bot
from telebot import types


def create_swapwallet_invoice(amount_toman, order_id, description="پرداخت"):
    api_key  = setting_get("swapwallet_api_key", "").strip()
    username = setting_get("swapwallet_username", "").strip()
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()
    if username.startswith("@"):
        username = username[1:].strip()
    if not api_key:
        return False, {"error": "کلید API سواپ ولت تنظیم نشده است. از پنل مدیریت ← تنظیمات ← درگاه‌ها اقدام کنید."}
    if not username:
        return False, {"error": "نام کاربری فروشگاه سواپ ولت تنظیم نشده است. از پنل مدیریت ← تنظیمات ← درگاه‌ها اقدام کنید."}
    payload = json.dumps({
        "amount":      {"number": str(int(amount_toman)), "unit": "IRT"},
        "ttl":         3600,
        "orderId":     str(order_id),
        "description": str(description),
        "userLanguage": "FA",
    }, ensure_ascii=False).encode("utf-8")
    safe_user = urllib.parse.quote(username, safe="")
    url = f"{SWAPWALLET_BASE_URL}/v1/payment/{safe_user}/resid"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent":   "ConfigFlow/1.0",
        "Accept":       "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("id"):
            result["_order_id"] = str(order_id)
            return True, result
        return False, {"error": str(result)[:300]}
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            msg = err_data.get("message") or err_data.get("error") or str(err_data)[:200]
        except Exception:
            msg = f"HTTP {e.code}: {e.reason}"
        return False, {"error": msg}
    except Exception as e:
        return False, {"error": str(e)}


def check_swapwallet_invoice(order_id):
    api_key  = setting_get("swapwallet_api_key", "").strip()
    username = setting_get("swapwallet_username", "").strip()
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()
    if username.startswith("@"):
        username = username[1:].strip()
    if not username:
        return False, {"error": "نام کاربری فروشگاه سواپ ولت تنظیم نشده است."}
    if not api_key:
        return False, {"error": "کلید API سواپ ولت تنظیم نشده است."}
    safe_user  = urllib.parse.quote(username, safe="")
    safe_order = urllib.parse.quote(str(order_id), safe="")
    url = f"{SWAPWALLET_BASE_URL}/v2/payment/{safe_user}/invoices/with-order-id/{safe_order}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent":    "ConfigFlow/1.0",
        "Accept":        "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "OK":
            return True, data.get("result", data)
        return False, {"error": str(data)[:300]}
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            msg = err_data.get("message") or err_data.get("error") or str(err_data)[:200]
        except Exception:
            msg = f"HTTP {e.code}: {e.reason}"
        return False, {"error": msg}
    except Exception as e:
        return False, {"error": str(e)}


def show_swapwallet_page(call, *, amount_toman, invoice_id, payment_links,
                          payment_id, verify_cb, **kwargs):
    """Render the SwapWallet Resid payment page."""
    from ..ui.helpers import send_or_edit
    short_id = invoice_id.replace("-", "")[:10] if invoice_id else "---"
    text = (
        "🏦 <b>پرداخت آنلاین ریالی (SwapWallet)</b>\n\n"
        f"🛒 کد پیگیری: <code>{short_id}</code>\n"
        f"💰 مبلغ: <b>{fmt_price(amount_toman)}</b> تومان\n\n"
        "✅ فاکتور پرداخت ایجاد شد.\n"
        "از یکی از لینک‌های زیر پرداخت را انجام دهید:\n\n"
        "❌ این فاکتور <b>۱ ساعت</b> اعتبار دارد\n"
        "پس از پرداخت، دکمه «✅ بررسی پرداخت» را بزنید."
    )
    kb = types.InlineKeyboardMarkup()
    for link in payment_links:
        link_type = link.get("type", "")
        link_url  = link.get("url", "")
        if not link_url:
            continue
        if link_type == "TELEGRAM_WEBAPP":
            kb.add(types.InlineKeyboardButton("💳 پرداخت در تلگرام", url=link_url))
        elif link_type == "WEBSITE":
            kb.add(types.InlineKeyboardButton("🌐 پرداخت از مرورگر", url=link_url))
        else:
            kb.add(types.InlineKeyboardButton(f"🔗 {link_type}", url=link_url))
    kb.add(types.InlineKeyboardButton("✅ بررسی پرداخت", callback_data=verify_cb))
    kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="nav:main"))
    bot.answer_callback_query(call.id)
    send_or_edit(call, text, kb)


def swapwallet_error_page(call, err_msg):
    """Show a descriptive error message for SwapWallet failures."""
    from ..ui.helpers import send_or_edit
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="nav:main"))
    bot.answer_callback_query(call.id)
    send_or_edit(call,
        "❌ <b>خطا در ایجاد فاکتور پرداخت آنلاین ریالی (SwapWallet)</b>\n\n"
        f"<code>{esc(str(err_msg)[:400])}</code>\n\n"
        "⚠️ لطفاً موارد زیر را بررسی کنید:\n"
        "• نام کاربری فروشگاه <b>بدون @</b> وارد شده باشد\n"
        "• فروشگاه در پنل سواپ ولت ایجاد شده باشد\n"
        "• کلید API معتبر باشد (در صورت نیاز)",
        kb)

