# -*- coding: utf-8 -*-
"""
TronPays Rial payment gateway — create and check invoices via REST API.
API docs: https://api.tronpays.online/docs#/
"""

import json
import hashlib
import urllib.request
import urllib.error

from ..db import setting_get


TRONPAYS_RIAL_BASE_URL = "https://api.tronpays.online"


def _make_hash_id(raw: str) -> str:
    """Return a <=20-char hash derived from raw — satisfies TronPays max-20 constraint."""
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:20]


def _decode_response_body(resp) -> tuple[str, object]:
    """
    Read response and try to parse JSON.
    Returns: (raw_text, parsed_data_or_raw_text)
    """
    raw = resp.read().decode("utf-8", errors="replace").strip()
    if not raw:
        return "", ""

    try:
        return raw, json.loads(raw)
    except Exception:
        return raw, raw


def _extract_error_message(data) -> str:
    """Extract a readable error message from API error payload."""
    if isinstance(data, dict):
        if "detail" in data:
            try:
                return json.dumps(data["detail"], ensure_ascii=False)[:500]
            except Exception:
                return str(data["detail"])[:500]
        if "message" in data:
            return str(data["message"])[:500]
        return json.dumps(data, ensure_ascii=False)[:500]

    if isinstance(data, list):
        try:
            return json.dumps(data, ensure_ascii=False)[:500]
        except Exception:
            return str(data)[:500]

    return str(data)[:500]


def _post_tronpays(path: str, payload: dict, timeout: int = 15):
    """
    Send POST request to TronPays.
    Returns: (success: bool, parsed_response: object)
    """
    url = f"{TRONPAYS_RIAL_BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "ConfigFlow/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _, parsed = _decode_response_body(resp)
        return True, parsed

    except urllib.error.HTTPError as e:
        try:
            raw_body = e.read().decode("utf-8", errors="replace").strip()
            try:
                parsed = json.loads(raw_body) if raw_body else {}
            except Exception:
                parsed = raw_body or f"HTTP {e.code}: {e.reason}"
        except Exception:
            parsed = f"HTTP {e.code}: {e.reason}"

        return False, {"error": _extract_error_message(parsed), "status_code": e.code, "raw": parsed}

    except Exception as e:
        return False, {"error": str(e)}


def create_tronpays_rial_invoice(amount_toman, hash_id, description=""):
    """
    Create a TronPays invoice.

    Returns:
        (True, response_data) on success
        (False, {"error": ...}) on failure

    Note:
        Based on current docs, the success response schema is documented as "string",
        so we return the raw/parsed API response instead of assuming fixed keys like
        invoice_id or invoice_url.
    """
    api_key = setting_get("tronpays_rial_api_key", "").strip()
    if not api_key:
        return False, {
            "error": "کلید API تران‌پیز ثبت نشده است. از پنل مدیریت ← تنظیمات ← درگاه‌ها اقدام کنید."
        }

    callback_url = setting_get("tronpays_rial_callback_url", "").strip() or "https://example.com/"
    safe_hash_id = _make_hash_id(str(hash_id))

    payload = {
        "api_key": api_key,
        "hash_id": safe_hash_id,
        "amount": int(amount_toman),
        "callback_url": callback_url,
    }

    success, result = _post_tronpays("/api/invoice/create", payload)

    if not success:
        return False, result

    return True, result


def check_tronpays_rial_invoice(invoice_id):
    """
    Check the status of a TronPays invoice.

    Returns:
        (True, response_data) on success
        (False, {"error": ...}) on failure
    """
    api_key = setting_get("tronpays_rial_api_key", "").strip()
    if not api_key:
        return False, {"error": "کلید API ثبت نشده است."}

    payload = {
        "api_key": api_key,
        "invoice_id": str(invoice_id),
    }

    success, result = _post_tronpays("/api/invoice/check", payload)

    if not success:
        return False, result

    return True, result


def is_tronpays_paid(status) -> bool:
    """
    Best-effort detection of successful payment from TronPays check response.

    Since the current docs show the 200-response schema as 'string', this function
    supports both string and dict responses.
    """
    if isinstance(status, dict):
        # Backward-compatible / best-effort checks
        if status.get("paid") is True:
            return True

        for key in ("status", "state", "payment_status"):
            value = status.get(key)
            if isinstance(value, str) and value.strip().lower() in {
                "paid", "success", "successful", "completed", "done"
            }:
                return True

        return False

    if isinstance(status, str):
        normalized = status.strip().lower()
        return normalized in {
            "paid", "success", "successful", "completed", "done"
        }

    return False