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

active_client = {}
waiting_note = {}

# ---------- МЕНЮ ----------
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Клиенты")],
        [KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True
)

status_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🟢 Новые"), KeyboardButton(text="🟡 В работе")],
        [KeyboardButton(text="🔴 Закрытые"), KeyboardButton(text="📋 Все")],
    ],
    resize_keyboard=True
)

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message):
    active_client.pop(message.from_user.id, None)
    if message.from_user.id == OWNER_ID:
        await message.answer("Админ-меню открыто.", reply_markup=admin_menu)
    else:
        get_or_create_client(message.from_user.id, message.from_user.full_name)
        await message.answer("Здравствуйте! Напишите сообщение — администратор ответит.")

# ---------- ПОМОЩЬ ----------
@dp.message(F.text == "ℹ️ Помощь")
async def help_menu(message: Message):
    await message.answer(
        "📘 Инструкция\n\n"
        "1️⃣ Клиенты — список клиентов\n"
        "2️⃣ Выберите статус для фильтрации\n"
        "3️⃣ Нажмите клиента → ✉️ Написать\n"
        "4️⃣ После диалога — ✅ Завершить чат\n\n"
        "Reply работает как запасной вариант."
    )

# ---------- КЛИЕНТЫ ----------
@dp.message(F.text == "📋 Клиенты")
async def clients_root(message: Message):
    await message.answer("Выберите статус:", reply_markup=status_menu)

def show_clients(message: Message, status=None):
    clients = get_clients(status)
    if not clients:
        return message.answer("Клиентов нет.")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{name} ({st})",
                callback_data=f"client:{uid}"
            )]
            for uid, name, st in clients
        ]
    )
    return message.answer("📋 Клиенты:", reply_markup=keyboard)

@dp.message(F.text == "🟢 Новые")
async def show_new(message: Message):
    await show_clients(message, "new")

@dp.message(F.text == "🟡 В работе")
async def show_work(message: Message):
    await show_clients(message, "work")

@dp.message(F.text == "🔴 Закрытые")
async def show_closed(message: Message):
    await show_clients(message, "closed")

@dp.message(F.text == "📋 Все")
async def show_all(message: Message):
    await show_clients(message)

# ---------- КАРТОЧКА ----------
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
            [InlineKeyboardButton(text="📝 Заметка", callback_data=f"note:{user_id}")],
            [InlineKeyboardButton(text="✅ Завершить чат", callback_data="finish")]
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

# ---------- НАПИСАТЬ ----------
@dp.callback_query(F.data.startswith("write:"))
async def write_client(callback):
    await callback.answer()
    active_client[callback.from_user.id] = int(callback.data.split(":")[1])
    await callback.message.answer("✉️ Введите сообщение для клиента.")

# ---------- СТАТУС ----------
@dp.callback_query(F.data.startswith("status:"))
async def change_status(callback):
    await callback.answer()
    _, uid, st = callback.data.split(":")
    update_status(int(uid), st)
    await callback.message.answer("✅ Статус обновлён.")

# ---------- ЗАВЕРШИТЬ ----------
@dp.callback_query(F.data == "finish")
async def finish_chat(callback):
    await callback.answer()
    active_client.pop(callback.from_user.id, None)
    await callback.message.answer("✅ Чат завершён.")

# ---------- ЗАМЕТКА ----------
@dp.callback_query(F.data.startswith("note:"))
async def note_start(callback):
    await callback.answer()
    waiting_note[callback.from_user.id] = int(callback.data.split(":")[1])
    await callback.message.answer("📝 Введите заметку.")

# ---------- ТЕКСТ ----------
@dp.message(F.text & ~F.reply_to_message)
async def text_handler(message: Message):
    if message.from_user.id in waiting_note:
        uid = waiting_note.pop(message.from_user.id)
        update_note(uid, message.text)
        await message.answer("✅ Заметка сохранена.")
        return

    if message.from_user.id in active_client:
        uid = active_client[message.from_user.id]
        save_message(uid, "admin", message.text)
        await bot.send_message(uid, message.text)
        await message.answer("✅ Сообщение отправлено.")
        return

    if message.from_user.id != OWNER_ID:
        get_or_create_client(message.from_user.id, message.from_user.full_name)
        save_message(message.from_user.id, "client", message.text)
        await bot.send_message(
            OWNER_ID,
            f"📩 Новое сообщение\n{message.from_user.full_name}\nID: {message.from_user.id}\n\n{message.text}"
        )
        await message.answer("Сообщение отправлено администратору.")

# ---------- REPLY ----------
@dp.message(F.reply_to_message)
async def reply_handler(message: Message):
    if "ID:" not in message.reply_to_message.text:
        return
    uid = int(message.reply_to_message.text.split("ID:")[1].split()[0])
    save_message(uid, "admin", message.text)
    await bot.send_message(uid, message.text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
