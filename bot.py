import asyncio
import json
import os
import http.server
import socketserver
import threading
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatType
from aiogram.client.default import DefaultBotProperties

# ====== НАСТРОЙКИ ======
BOT_TOKEN = "8873918257:AAFxarw6WGvYjaBpb9KGWH0R-n7yH1rIueI"
ADMIN_ID = 922545502
GROUP_ID = -1004291975368

WELCOME_TEXT = (
    "👋 Добро пожаловать!\n\n"
    "Здесь ты можешь анонимно пообщаться с администрацией.\n\n"
    "Выбери, что тебе нужно:"
)
# =======================

DB_FILE = "users.json"
STATS_FILE = "stats.json"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# --- База пользователей ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Счётчик сообщений ---
def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"incoming": 0, "outgoing": 0}
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(data):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def inc_incoming():
    s = load_stats()
    s["incoming"] = s.get("incoming", 0) + 1
    save_stats(s)

def inc_outgoing():
    s = load_stats()
    s["outgoing"] = s.get("outgoing", 0) + 1
    save_stats(s)

def find_user_by_topic(topic_id: int):
    db = load_db()
    for uid, info in db.items():
        if info.get("topic_id") == topic_id:
            return int(uid)
    return None

def get_next_number(db):
    numbers = [info.get("number", 0) for info in db.values() if info.get("number")]
    return max(numbers, default=0) + 1

def find_user_by_number(number: int):
    db = load_db()
    for uid, info in db.items():
        if info.get("number") == number:
            return int(uid), info
    return None, None

# --- Клавиатуры ---
def kb_topics():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="topic:Поддержка")],
        [InlineKeyboardButton(text="🗣 Общение", callback_data="topic:Общение")],
        [InlineKeyboardButton(text="💬 Поддержка/Общение", callback_data="topic:Поддержка/Общение")],
        [InlineKeyboardButton(text="🎭 Ролка", callback_data="topic:Ролка")]
    ])

def kb_gender():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👦 Парень", callback_data="gender:Парень")],
        [InlineKeyboardButton(text="👧 Девушка", callback_data="gender:Девушка")]
    ])

# --- Создание темы ---
async def create_topic(user_id: int, topic_name: str, gender: str, username: str):
    db = load_db()

    if str(user_id) in db and db[str(user_id)].get("topic_id"):
        return db[str(user_id)]["topic_id"]

    number = get_next_number(db)
    full_name = f"👤 Аноним #{number} | {topic_name} | {gender}"
    topic = await bot.create_forum_topic(chat_id=GROUP_ID, name=full_name)
    topic_id = topic.message_thread_id

    if str(user_id) not in db:
        db[str(user_id)] = {}

    db[str(user_id)].update({
        "number": number,
        "topic_id": topic_id,
        "username": username,
        "topic_name": topic_name,
        "gender": gender,
        "blocked": False,
        "registered": True
    })
    save_db(db)

    await bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=topic_id,
        text=(
            f"🆕 <b>Новое обращение</b>\n\n"
            f"🔢 Номер: <b>#{number}</b>\n"
            f"📋 Тема: <b>{topic_name}</b>\n"
            f"👤 Пол: <b>{gender}</b>"
        )
    )
    return topic_id
# --- /start ---
@dp.message(F.chat.type == ChatType.PRIVATE, F.text == "/start")
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        await message.answer(
            "Привет, админ! Команды:\n"
            "/stats — статистика\n"
            "/blocked — список заблокированных\n"
            "/find НОМЕР — найти по номеру\n"
            "/unban НОМЕР — разблокировать по номеру\n"
            "/broadcast текст — рассылка"
        )
        return

    db = load_db()
    if str(user_id) in db and db[str(user_id)].get("registered"):
        await message.answer("Вы уже зарегистрированы. Просто напишите сообщение.")
        return

    await message.answer(WELCOME_TEXT, reply_markup=kb_topics())

# --- Выбор темы ---
@dp.callback_query(F.data.startswith("topic:"))
async def cb_topic(callback: CallbackQuery):
    topic_name = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    db = load_db()
    if str(user_id) not in db:
        db[str(user_id)] = {}
    db[str(user_id)]["pending_topic"] = topic_name
    save_db(db)

    await callback.message.edit_text(
        f"Ты выбрал: <b>{topic_name}</b>\n\nТеперь укажи пол:",
        reply_markup=kb_gender()
    )
    await callback.answer()

# --- Выбор пола ---
@dp.callback_query(F.data.startswith("gender:"))
async def cb_gender(callback: CallbackQuery):
    gender = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    db = load_db()
    topic_name = db.get(str(user_id), {}).get("pending_topic", "Общение")
    username = callback.from_user.username or callback.from_user.first_name or "user"

    await create_topic(user_id, topic_name, gender, username)

    db = load_db()
    if "pending_topic" in db.get(str(user_id), {}):
        del db[str(user_id)]["pending_topic"]
        save_db(db)

    await callback.message.edit_text(
        f"✅ Готово!\n\n📋 Тема: <b>{topic_name}</b>\n👤 Пол: <b>{gender}</b>\n\n"
        f"Теперь можешь писать сообщение — оно уйдёт администратору."
    )
    await callback.answer()

# --- Сообщение от пользователя ---
@dp.message(F.chat.type == ChatType.PRIVATE)
async def user_message(message: Message):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        if message.text and message.text.startswith("/"):
            await handle_admin_command(message)
        return

    db = load_db()

    if str(user_id) not in db or not db[str(user_id)].get("registered"):
        await message.answer(
            "👋 Сначала выбери, что тебе нужно:",
            reply_markup=kb_topics()
        )
        return

    if db[str(user_id)].get("blocked"):
        await message.answer("🚫 Вы заблокированы. Обратитесь к администратору.")
        return

    topic_id = db[str(user_id)].get("topic_id")
    if not topic_id:
        await message.answer("❌ Тема не найдена. Напиши /start заново.")
        return

    try:
        await bot.copy_message(
            chat_id=GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
        inc_incoming()  # +1 к входящим
    except Exception as e:
        print(f"Ошибка копирования: {e}")

# --- Команды админа в личке ---
async def handle_admin_command(message: Message):
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    db = load_db()

    if cmd == "/stats":
        total = len([u for u in db.values() if u.get("registered")])
        blocked = sum(1 for v in db.values() if v.get("blocked"))
        clean = total - blocked
        s = load_stats()
        await message.answer(
            f"📊 <b>Статистика</b>\n\n"
            f"👥 Всего: <b>{total}</b>\n"
            f"✅ Чистых: <b>{clean}</b>\n"
            f"🚫 Заблокированных: <b>{blocked}</b>\n\n"
            f"📥 Входящих: <b>{s.get('incoming', 0)}</b>\n"
            f"📤 Исходящих: <b>{s.get('outgoing', 0)}</b>"
        )
        return
    if cmd == "/blocked":
        blocked_list = [(uid, v) for uid, v in db.items() if v.get("blocked")]
        if not blocked_list:
            await message.answer("✅ Заблокированных нет.")
            return
        out = "🚫 <b>Заблокированные:</b>\n\n"
        for uid, info in blocked_list:
            num = info.get("number", "?")
            out += f"• Номер <b>#{num}</b> — ID <code>{uid}</code>\n"
        out += "\nРазблокировать: <code>/unban НОМЕР</code>"
        await message.answer(out)
        return

    if cmd == "/find":
        if len(parts) < 2:
            await message.answer("Используй: /find НОМЕР")
            return
        try:
            num = int(parts[1].strip().replace("#", ""))
        except ValueError:
            await message.answer("❌ Номер должен быть числом.")
            return
        uid, info = find_user_by_number(num)
        if not uid:
            await message.answer(f"❌ Пользователь #{num} не найден.")
            return
        await message.answer(
            f"🔍 <b>Найден пользователь</b>\n\n"
            f"🔢 Номер: <b>#{num}</b>\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"👤 Юзернейм: @{info.get('username', 'нет')}\n"
            f"📋 Тема: <b>{info.get('topic_name', '—')}</b>\n"
            f"👤 Пол: <b>{info.get('gender', '—')}</b>\n"
            f"🚫 Заблокирован: <b>{'Да' if info.get('blocked') else 'Нет'}</b>"
        )
        return

    if cmd == "/unban":
        if len(parts) < 2:
            await message.answer("Используй: /unban НОМЕР")
            return
        try:
            num = int(parts[1].strip().replace("#", ""))
        except ValueError:
            await message.answer("❌ Номер должен быть числом.")
            return
        uid, info = find_user_by_number(num)
        if not uid:
            await message.answer(f"❌ Пользователь #{num} не найден.")
            return
        db[str(uid)]["blocked"] = False
        save_db(db)
        topic_id = info.get("topic_id")
        if topic_id:
            try:
                await bot.send_message(
                    chat_id=GROUP_ID,
                    message_thread_id=topic_id,
                    text="✅ Пользователь разблокирован."
                )
            except Exception:
                pass
        await message.answer(f"✅ Пользователь #{num} (ID {uid}) разблокирован.")
        return

    if cmd == "/broadcast":
        if len(parts) < 2:
            await message.answer(
                "📢 <b>Рассылка</b>\n\n"
                "Используй: <code>/broadcast Текст</code>"
            )
            return
        broadcast_text = parts[1].strip()
        users = [uid for uid, v in db.items() if v.get("registered") and not v.get("blocked")]
        sent = 0
        failed = 0
        status_msg = await message.answer(f"📤 Отправляю... 0/{len(users)}")
        for i, uid in enumerate(users, 1):
            try:
                await bot.send_message(int(uid), f"📢 <b>Сообщение от админа:</b>\n\n{broadcast_text}")
                sent += 1
            except Exception:
                failed += 1
            if i % 10 == 0:
                try:
                    await status_msg.edit_text(f"📤 Отправляю... {i}/{len(users)}")
                except Exception:
                    pass
            await asyncio.sleep(0.05)
        await status_msg.edit_text(
            f"✅ <b>Рассылка завершена</b>\n\n"
            f"📤 Отправлено: <b>{sent}</b>\n"
            f"❌ Не доставлено: <b>{failed}</b>"
        )
        return

# --- Команды админа в группе (тема) ---
@dp.message(F.chat.id == GROUP_ID)
async def admin_group(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.message_thread_id:
        return

    user_id = find_user_by_topic(message.message_thread_id)
    if not user_id:
        return

    text = (message.text or "").strip()
    if text == "/ban":
        db = load_db()
        if str(user_id) in db:
            db[str(user_id)]["blocked"] = True
            save_db(db)
            num = db[str(user_id)].get("number", "?")
            await message.reply(f"🚫 Пользователь #{num} заблокирован.")
        return

    if text == "/unban":
        db = load_db()
        if str(user_id) in db:
            db[str(user_id)]["blocked"] = False
            save_db(db)
            num = db[str(user_id)].get("number", "?")
            await message.reply(f"✅ Пользователь #{num} разблокирован.")
        return

    if text.startswith("/"):
        return

    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        inc_outgoing()  # +1 к исходящим
    except Exception as e:
        print(f"Ошибка отправки: {e}")

# --- Запуск ---
def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Dummy server started on port {port}")
        httpd.serve_forever()

async def main():
    threading.Thread(target=start_dummy_server, daemon=True).start()
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
