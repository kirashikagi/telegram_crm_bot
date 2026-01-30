import os
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database import (
    add_admin,
    remove_admin,
    is_admin,
    is_owner,
    get_admins,
    get_or_create_client,
    update_status,
    update_note,
    get_clients,
    get_client,
    save_message,
    get_history,
)

# ---------- ENV ----------
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

waiting_note_for = {}

# ---------- MENUS ----------
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Клиенты")],
        [KeyboardButton(text="👥 Админы")],
    ],
    resize_keyboard=True
)

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.id == OWNER_ID:
        add_admin(OWNER_ID, owner=True)

    if is_admin(message.from_user.id):
        await message.answer("Админ-режим активирован.", reply_markup=admin_menu)
    else:
        get_or_create_client(message.from_user.id, message.from_user.full_name)
        await message.answer(
            "Здравствуйте! Напишите сообщение — администратор скоро ответит."
        )

# ---------- ADMINS ----------
@dp.message(F.text == "👥 Админы")
async def admins_menu(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Только главный админ.")
        return

    admins = get_admins()
    text = "👥 Админы:\n\n"
    for uid, owner in admins:
        text += f"{uid} {'(главный)' if owner else ''}\n"

    await message.answer(
        text +
        "\n➕ Добавить: /add_admin ID\n➖ Удалить: /del_admin ID"
    )


@dp.message(F.text.startswith("/add_admin"))
async def add_admin_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        add_admin(uid)
        await message.answer("✅ Админ добавлен.")
    except Exception:
        await message.answer("❌ Используй: /add_admin ID")


@dp.message(F.text.startswith("/del_admin"))
async def del_admin_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return
    try:
        uid = int(message.text.split()[1])
        remove_admin(uid)
        await message.answer("✅ Админ удалён.")
    except Exception:
        await message.answer("❌ Используй: /del_admin ID")

# ---------- CLIENTS ----------
@dp.message(F.text == "📋 Клиенты")
async def clients_menu(message: Message):
    if not is_admin(message.from_user.id):
        return

    clients = get_clients()
    if not clients:
        await message.answer("Клиентов нет.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{name} ({status})",
                callback_data=f"client:{uid}"
            )]
            for uid, name, status in clients
        ]
    )

    await message.answer("📋 Клиенты:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("client:"))
async def client_card(callback):
    await callback.answer()

    if not is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[1])
    name, status, note = get_client(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Новый", callback_data=f"status:{user_id}:new"),
                InlineKeyboardButton(text="🟡 В работе", callback_data=f"status:{user_id}:work"),
                InlineKeyboardButton(text="🔴 Закрыт", callback_data=f"status:{user_id}:closed"),
            ],
            [InlineKeyboardButton(text="📝 Заметка", callback_data=f"note:{user_id}")]
        ]
    )

    await callback.message.answer(
        f"👤 {name}\n📌 Статус: {status}\n📝 Заметка: {note or '—'}",
        reply_markup=keyboard
    )

    history = get_history(user_id)
    if history:
        await callback.message.answer(
            "\n".join(
                [("👤 " if s == "client" else "🧑‍💼 ") + m for s, m in history]
            )
        )

# ---------- STATUS ----------
@dp.callback_query(F.data.startswith("status:"))
async def change_status(callback):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return

    _, user_id, status = callback.data.split(":")
    update_status(int(user_id), status)
    await callback.message.answer("✅ Статус обновлён.")

# ---------- NOTE ----------
@dp.callback_query(F.data.startswith("note:"))
async def note_start(callback):
    await callback.answer()
    waiting_note_for[callback.from_user.id] = int(callback.data.split(":")[1])
    await callback.message.answer(
        "📝 Введите заметку. Следующее сообщение будет сохранено."
    )

# ---------- TEXT HANDLER ----------
@dp.message(F.text & ~F.reply_to_message)
async def text_handler(message: Message):
    # ---- note from admin ----
    if is_admin(message.from_user.id) and message.from_user.id in waiting_note_for:
        client_id = waiting_note_for.pop(message.from_user.id)
        update_note(client_id, message.text)
        await message.answer("✅ Заметка сохранена.")
        return

    # ---- message from client ----
    if not is_admin(message.from_user.id):
        get_or_create_client(message.from_user.id, message.from_user.full_name)
        save_message(message.from_user.id, "client", message.text)

        await bot.send_message(
            OWNER_ID,
            f"📩 Новое сообщение\n"
            f"{message.from_user.full_name}\n"
            f"ID: {message.from_user.id}\n\n"
            f"{message.text}"
        )
        await message.answer("Сообщение отправлено администратору.")

# ---------- REPLY ----------
@dp.message(F.reply_to_message)
async def reply_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    original = message.reply_to_message.text
    if "ID:" not in original:
        return

    client_id = int(original.split("ID:")[1].split()[0])
    save_message(client_id, "admin", message.text)
    await bot.send_message(client_id, message.text)

# ---------- MAIN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
