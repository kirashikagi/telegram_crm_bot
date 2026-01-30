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
    get_or_create_client,
    get_clients,
    get_client,
    update_status,
    update_note,
    save_message,
    get_history,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# активный клиент для админа
active_client = {}
# ожидание заметки
waiting_note = {}

admin_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📋 Клиенты")]],
    resize_keyboard=True
)


@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.id == OWNER_ID:
        await message.answer("Админ-режим активирован.", reply_markup=admin_menu)
    else:
        get_or_create_client(message.from_user.id, message.from_user.full_name)
        await message.answer("Здравствуйте! Напишите сообщение — администратор ответит.")


# ---------- СПИСОК КЛИЕНТОВ ----------
@dp.message(F.text == "📋 Клиенты")
async def clients_menu(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    clients = get_clients()
    if not clients:
        await message.answer("Клиентов пока нет.")
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


# ---------- КАРТОЧКА КЛИЕНТА ----------
@dp.callback_query(F.data.startswith("client:"))
async def client_card(callback):
    await callback.answer()

    user_id = int(callback.data.split(":")[1])
    name, status, note = get_client(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Написать клиенту", callback_data=f"write:{user_id}")],
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


# ---------- НАПИСАТЬ КЛИЕНТУ ----------
@dp.callback_query(F.data.startswith("write:"))
async def write_client(callback):
    await callback.answer()
    client_id = int(callback.data.split(":")[1])
    active_client[callback.from_user.id] = client_id
    await callback.message.answer("✉️ Введите сообщение для клиента.")


# ---------- СТАТУС ----------
@dp.callback_query(F.data.startswith("status:"))
async def change_status(callback):
    await callback.answer()
    _, user_id, status = callback.data.split(":")
    update_status(int(user_id), status)
    await callback.message.answer("✅ Статус обновлён.")


# ---------- ЗАМЕТКА ----------
@dp.callback_query(F.data.startswith("note:"))
async def note_start(callback):
    await callback.answer()
    waiting_note[callback.from_user.id] = int(callback.data.split(":")[1])
    await callback.message.answer("📝 Введите заметку. Следующее сообщение сохранится.")


# ---------- ТЕКСТ ----------
@dp.message(F.text & ~F.reply_to_message)
async def text_handler(message: Message):
    # заметка
    if message.from_user.id in waiting_note:
        client_id = waiting_note.pop(message.from_user.id)
        update_note(client_id, message.text)
        await message.answer("✅ Заметка сохранена.")
        return

    # сообщение активному клиенту
    if message.from_user.id in active_client:
        client_id = active_client[message.from_user.id]
        save_message(client_id, "admin", message.text)
        await bot.send_message(client_id, message.text)
        await message.answer("✅ Сообщение отправлено клиенту.")
        return

    # сообщение от клиента
    if message.from_user.id != OWNER_ID:
        get_or_create_client(message.from_user.id, message.from_user.full_name)
        save_message(message.from_user.id, "client", message.text)
        await bot.send_message(
            OWNER_ID,
            f"📩 Новое сообщение\n{message.from_user.full_name}\nID: {message.from_user.id}\n\n{message.text}"
        )
        await message.answer("Сообщение отправлено администратору.")


# ---------- REPLY (ЗАПАСНОЙ ВАРИАНТ) ----------
@dp.message(F.reply_to_message)
async def reply_handler(message: Message):
    if "ID:" not in message.reply_to_message.text:
        return

    client_id = int(message.reply_to_message.text.split("ID:")[1].split()[0])
    save_message(client_id, "admin", message.text)
    await bot.send_message(client_id, message.text)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
