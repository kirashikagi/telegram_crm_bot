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

# ---------- ENV ----------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------- STATE ----------
active_client = {}      # admin_id -> client_id
waiting_note = {}       # admin_id -> client_id

# ---------- MENUS ----------
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Клиенты")],
        [KeyboardButton(text="ℹ️ Помощь")],
        [KeyboardButton(text="🔄 Главное меню")],
    ],
    resize_keyboard=True
)

status_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🟢 Новые"), KeyboardButton(text="🟡 В работе")],
        [KeyboardButton(text="🔴 Закрытые"), KeyboardButton(text="📋 Все")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True
)

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message):
    active_client.pop(message.from_user.id, None)
    if message.from_user.id == OWNER_ID:
        await message.answer(
            "Админ-меню открыто.",
            reply_markup=main_menu
        )
    else:
        get_or_create_client(message.from_user.id, message.from_user.full_name)
        await message.answer(
            "Здравствуйте! Напишите сообщение — администратор ответит."
        )

# ---------- BACK / MAIN ----------
@dp.message(F.text.in_(["⬅️ Назад", "🔄 Главное меню"]))
async def back_to_main(message: Message):
    active_client.pop(message.from_user.id, None)
    await message.answer(
        "Главное меню.",
        reply_markup=main_menu
    )

# ---------- HELP ----------
@dp.message(F.text == "ℹ️ Помощь")
async def help_menu(message: Message):
    await message.answer(
        "📘 Инструкция для администратора\n\n"
        "1️⃣ Клиенты — открыть список клиентов\n"
        "2️⃣ Выберите статус для фильтрации\n"
        "3️⃣ Откройте клиента → ✉️ Написать клиенту\n"
        "4️⃣ Напишите сообщение\n"
        "5️⃣ После диалога нажмите ✅ Завершить чат\n\n"
        "Reply (свайп по сообщению) работает как запасной вариант.\n"
        "Если клиент не выбран — бот никому не пишет.",
        reply_markup=main_menu
    )

# ---------- CLIENTS ROOT ----------
@dp.message(F.text == "📋 Клиенты")
async def clients_root(message: Message):
    await message.answer(
        "Выберите статус для фильтрации:",
        reply_markup=status_menu
    )

# ---------- SHOW CLIENTS ----------
async def show_clients(message: Message, status=None):
    clients = get_clients(status)
    if not clients:
        await message.answer(
            "Клиентов нет.",
            reply_markup=main_menu
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{name} ({st})",
                callback_data=f"client:{uid}"
            )]
            for uid, name, st in clients
        ]
    )

    await message.answer(
        "📋 Клиенты:",
        reply_markup=keyboard
    )
    await message.answer(
        "Главное меню.",
        reply_markup=main_menu
    )

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

# ---------- CLIENT CARD ----------
@dp.callback_query(F.data.startswith("client:"))
async def client_card(callback):
    await callback.answer()
    user_id = int(callback.data.split(":")[1])
    name, status, note = get_client(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✉️ Написать клиенту",
                callback_data=f"write:{user_id}"
            )],
            [
                InlineKeyboardButton(
                    text="🟢 Новый",
                    callback_data=f"status:{user_id}:new"
                ),
                InlineKeyboardButton(
                    text="🟡 В работе",
                    callback_data=f"status:{user_id}:work"
                ),
                InlineKeyboardButton(
                    text="🔴 Закрыт",
                    callback_data=f"status:{user_id}:closed"
                ),
            ],
            [InlineKeyboardButton(
                text="📝 Заметка",
                callback_data=f"note:{user_id}"
            )],
            [InlineKeyboardButton(
                text="✅ Завершить чат",
                callback_data="finish"
            )],
        ]
    )

    await callback.message.answer(
        f"👤 {name}\n"
        f"📌 Статус: {status}\n"
        f"📝 Заметка: {note or '—'}",
        reply_markup=keyboard
    )

    history = get_history(user_id)
    if history:
        await callback.message.answer(
            "\n".join(
                [("👤 " if s == "client" else "🧑‍💼 ") + m for s, m in history]
            )
        )

# ---------- WRITE ----------
@dp.callback_query(F.data.startswith("write:"))
async def write_client(callback):
    await callback.answer()
    active_client[callback.from_user.id] = int(
        callback.data.split(":")[1]
    )
    await callback.message.answer(
        "✉️ Введите сообщение для клиента."
    )

# ---------- FINISH CHAT ----------
@dp.callback_query(F.data == "finish")
async def finish_chat(callback):
    await callback.answer()
    active_client.pop(callback.from_user.id, None)
    await callback.message.answer(
        "✅ Чат завершён.",
        reply_markup=main_menu
    )

# ---------- STATUS ----------
@dp.callback_query(F.data.startswith("status:"))
async def change_status(callback):
    await callback.answer()
    _, uid, st = callback.data.split(":")
    update_status(int(uid), st)
    await callback.message.answer("✅ Статус обновлён.")

# ---------- NOTE ----------
@dp.callback_query(F.data.startswith("note:"))
async def note_start(callback):
    await callback.answer()
    waiting_note[callback.from_user.id] = int(
        callback.data.split(":")[1]
    )
    await callback.message.answer(
        "📝 Введите заметку."
    )

# ---------- TEXT ----------
@dp.message(F.text & ~F.reply_to_message)
async def text_handler(message: Message):
    # заметка
    if message.from_user.id in waiting_note:
        uid = waiting_note.pop(message.from_user.id)
        update_note(uid, message.text)
        await message.answer(
            "✅ Заметка сохранена.",
            reply_markup=main_menu
        )
        return

    # сообщение активному клиенту
    if message.from_user.id in active_client:
        uid = active_client[message.from_user.id]
        save_message(uid, "admin", message.text)
        await bot.send_message(uid, message.text)
        await message.answer(
            "✅ Сообщение отправлено клиенту.",
            reply_markup=main_menu
        )
        return

    # сообщение от клиента
    if message.from_user.id != OWNER_ID:
        get_or_create_client(
            message.from_user.id,
            message.from_user.full_name
        )
        save_message(
            message.from_user.id,
            "client",
            message.text
        )
        await bot.send_message(
            OWNER_ID,
            f"📩 Новое сообщение\n"
            f"{message.from_user.full_name}\n"
            f"ID: {message.from_user.id}\n\n"
            f"{message.text}"
        )
        await message.answer(
            "Сообщение отправлено администратору."
        )

# ---------- REPLY (FALLBACK) ----------
@dp.message(F.reply_to_message)
async def reply_handler(message: Message):
    if "ID:" not in message.reply_to_message.text:
        return
    uid = int(
        message.reply_to_message.text
        .split("ID:")[1]
        .split()[0]
    )
    save_message(uid, "admin", message.text)
    await bot.send_message(uid, message.text)

# ---------- MAIN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
