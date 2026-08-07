from aiogram import types
from bot.utils.helpers import its_me
from bot.utils.registry import register_command
from bot.twin.menu import build_main_view


@register_command("!двойник_меню")
async def cmd_twin_menu(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    text, keyboard = await build_main_view()
    await message.reply(text, reply_markup=keyboard)
    return True
