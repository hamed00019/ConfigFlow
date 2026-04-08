# -*- coding: utf-8 -*-
"""
/start message handler.
"""
from ..db import ensure_user, notify_first_start_if_needed, get_user, setting_get
from ..helpers import state_clear, is_admin
from ..ui.helpers import check_channel_membership, channel_lock_message
from ..ui.menus import show_main_menu
from ..bot_instance import bot


@bot.message_handler(commands=["start"])
def start_handler(message):
    ensure_user(message.from_user)
    notify_first_start_if_needed(message.from_user)
    state_clear(message.from_user.id)

    # Bot status check (before everything else for non-admins)
    if not is_admin(message.from_user.id):
        bot_status = setting_get("bot_status", "on")
        if bot_status == "off":
            return
        if bot_status == "update":
            bot.send_message(
                message.chat.id,
                "🔄 <b>ربات در حال بروزرسانی است</b>\n\n"
                "فعلاً ربات در حال بروزرسانی می‌باشد، لطفاً بعداً اقدام نمایید. 🙏\n\n"
                "در صورتی که کار فوری دارید، می‌توانید با پشتیبانی در ارتباط باشید.",
                parse_mode="HTML"
            )
            return

    user = get_user(message.from_user.id)
    if user and user["status"] == "restricted":
        bot.send_message(
            message.chat.id,
            "🚫 <b>دسترسی محدود شده</b>\n\n"
            "شما از ربات محدود شده‌اید و نمی‌توانید از آن استفاده کنید.\n"
            "در صورت نیاز با پشتیبانی تماس بگیرید.",
            parse_mode="HTML"
        )
        return
    if not check_channel_membership(message.from_user.id):
        channel_lock_message(message)
        return
    show_main_menu(message)
