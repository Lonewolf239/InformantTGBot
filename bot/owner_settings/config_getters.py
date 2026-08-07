from bot.owner_settings.database import owner_settings_db


async def is_payments_enabled() -> bool:
    return await owner_settings_db.get_setting("payments_enabled")


async def is_auto_reply_enabled() -> bool:
    return await owner_settings_db.get_setting("auto_reply_enabled")


async def is_reply_to_owner() -> bool:
    return await owner_settings_db.get_setting("reply_to_owner")


async def is_twin_feedback_enabled() -> bool:
    return await owner_settings_db.get_setting("twin_feedback_enabled")
