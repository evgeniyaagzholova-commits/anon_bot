import asyncio
import json
import os
import http.server
import socketserver
import threading
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ChatType
from aiogram.client.default import DefaultBotProperties

# ====== НАСТРОЙКИ ======
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 922545502
GROUP_ID = -1004291975368
LOG_CHANNEL_ID = -1004378039855

# Ссылки
LINK_ANKETA = "http://t.me/Just_my_thoughts_anketa_bot"
LINK_CHANNEL = "https://t.me/+aG7myjG7KG5jYTFi"
LINK_SUPPORT = "https://t.me/Tehpodderzka_sweethome_bot"
LINK_REVIEWS = "https://t.me/+7yar-PgEeDAxN2Ey"

# Баннеры
BANNER_TOPIC = "https://i.ibb.co.com/Z42GnWK/photo-2026-09-24-22-57-48.jpg"
BANNER_GENDER = "https://i.ibb.co.com/ymsM3sDd/photo-2026-09-24-22-57-34.jpg"

WELCOME_TEXT = (
    "✧ Добро пожаловать в бот поддержки «Милый дом» ♡\n\n"
    "Здесь тебя всегда выслушают и поймут.\n\n"
    "✉ Напиши «Привет» — и с тобой свяжется первый свободный администратор.\n\n"
    "❋ Бот полностью анонимен.\n"
    "Можешь не указывать тег — просто будь собой.\n\n"
    "♡ Если тебе некомфортно с текущим админом — напиши:\n"
    "«Хочу другого админа»\n\n"
    "✦ Дом всегда рад тебе. Добро пожаловать ♡\n\n"
    "↓ Выбери, что тебе нужно:"
)

DB_FILE = "users.json"
STATS_FILE = "stats.json"
FLUD_FILE = "flud.json"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# --- База ---
def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_db(): return load_json(DB_FILE, {})
def save_db(d): save_json(DB_FILE, d)
def load_stats(): return load_json(STATS_FILE, {"incoming": 0, "outgoing": 0})
def save_stats(d): save_json(STATS_FILE, d)
def load_flud(): return load_json(FLUD_FILE, {})
def save_flud(d): save_json(FLUD_FILE, d)

def inc_incoming():
    s = load_stats(); s["incoming"] = s.get("incoming", 0) + 1; save_stats(s)

def inc_outgoing():
    s = load_stats(); s["outgoing"] = s.get("outgoing", 0) + 1; save_stats(s)

def find_user_by_topic(topic_id):
    db = load_db()
    for uid, info in db.items():
        if info.get("topic_id") == topic_id:
            return int(uid)
    return None

def get_next_number(db):
    nums = [i.get("number", 0) for i in db.values() if i.get("number")]
    return max(nums, default=0) + 1

def find_user_by_number(number):
    db = load_db()
    for uid, info in db.items():
        if info.get("number") == number:
            return int(uid), info
    return None, None

# --- Логирование ---
async def log_action(text):
    try:
        await bot.send_message(LOG_CHANNEL_ID, text)
    except Exception as e:
        print(f"Ошибка логирования: {e}")

# --- Клавиатуры ---
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✧ Анкета", url=LINK_ANKETA)],
        [InlineKeyboardButton(text="✦ Канал", url=LINK_CHANNEL)],
        [InlineKeyboardButton(text="♡ Поддержка", url=LINK_SUPPORT)],
        [InlineKeyboardButton(text="❋ Отзывы", url=LINK_REVIEWS)],
    ])

def kb_topics():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✧ Поддержка", callback_data="topic:Поддержка")],
        [InlineKeyboardButton(text="❋ Общение", callback_data="topic:Общение")],
        [InlineKeyboardButton(text="✦ Поддержка/Общение", callback_data="topic:Поддержка/Общение")],
        [InlineKeyboardButton(text="♡ Ролка", callback_data="topic:Ролка")],
    ])

def kb_gender():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✧ Парень", callback_data="gender:Парень")],
        [InlineKeyboardButton(text="❋ Девушка", callback_data="gender:Девушка")],
    ])

# --- Создание темы ---
async def create_topic(user_id, topic_name, gender, username):
    db = load_db()
    if str(user_id) in db and db[str(user_id)].get("topic_id"):
        return db[str(user_id)]["topic_id"]

    number = get_next_number(db)
    full_name = f"✧ Аноним #{number} | {topic_name} | Хочет: {gender}"
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
        "registered": True,
        "created_at": time.time(),
        "last_user_msg": 0,
        "last_auto_reply": 0,
    })
    save_db(db)

    await bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=topic_id,
        text=(
            f"✧ <b>Новое обращение</b>\n\n"
            f"№ Номер: <b>#{number}</b>\n"
            f"✦ Тема: <b>{topic_name}</b>\n"
            f"♡ Хочет админа: <b>{gender}</b>"
        )
    )
    await log_action(f"✧ Новая тема #{number} | Тема: {topic_name} | Хочет: {gender}")
    await notify_admin_new_topic(number, topic_name, gender)
    return topic_id

async def notify_admin_new_topic(number, topic_name, gender):
    try:
        await bot.send_message(
            ADMIN_ID,
            f"✦ <b>Новая тема</b>\n\n"
            f"№ <b>#{number}</b>\n"
            f"Тема: <b>{topic_name}</b>\n"
            f"Хочет админа: <b>{gender}</b>"
        )
    except Exception as e:
        print(f"Ошибка оповещения: {e}")

# --- /start ---
@dp.message(F.chat.type == ChatType.PRIVATE, F.text == "/start")
async def cmd_start(message: Message):
    uid = message.from_user.id
    if uid == ADMIN_ID:
        await message.answer(
            "✧ <b>Команды админа:</b>\n\n"
            "/stats — статистика\n"
            "/blocked — список заблокированных\n"
            "/find НОМЕР — найти по номеру\n"
            "/unban НОМЕР — разблокировать\n"
            "/broadcast текст — рассылка\n"
            "/help — эта справка"
        )
        return

    db = load_db()
    if str(uid) in db and db[str(uid)].get("registered"):
        await message.answer("✧ Вы уже зарегистрированы. Напишите сообщение.")
        return

    try:
        await bot.send_photo(
            chat_id=uid,
            photo=BANNER_TOPIC,
            caption=WELCOME_TEXT,
            reply_markup=kb_topics()
        )
    except Exception:
        await message.answer(WELCOME_TEXT, reply_markup=kb_topics())

# --- Выбор темы ---
@dp.callback_query(F.data.startswith("topic:"))
async def cb_topic(cb: CallbackQuery):
    topic_name = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    db = load_db()
    if str(uid) not in db: db[str(uid)] = {}
    db[str(uid)]["pending_topic"] = topic_name
    save_db(db)

    try:
        await bot.send_photo(
            chat_id=uid,
            photo=BANNER_GENDER,
            caption=f"✧ Ты выбрал: <b>{topic_name}</b>\n\n♡ Какого админа ты хочешь?",
            reply_markup=kb_gender()
        )
    except Exception:
        await cb.message.edit_text(
            f"✧ Ты выбрал: <b>{topic_name}</b>\n\n♡ Какого админа ты хочешь?",
            reply_markup=kb_gender()
        )
    await cb.answer()

# --- Выбор пола ---
@dp.callback_query(F.data.startswith("gender:"))
async def cb_gender(cb: CallbackQuery):
    gender = cb.data.split(":", 1)[1]
    uid = cb.from_user.id
    db = load_db()
    topic_name = db.get(str(uid), {}).get("pending_topic", "Общение")
    username = cb.from_user.username or cb.from_user.first_name or "user"

    await create_topic(uid, topic_name, gender, username)

    db = load_db()
    if "pending_topic" in db.get(str(uid), {}):
        del db[str(uid)]["pending_topic"]
        save_db(db)

    final_text = (
        f"✧ Готово!\n\n"
        f"✦ Тема: <b>{topic_name}</b>\n"
        f"♡ Хочешь админа: <b>{gender}</b>\n\n"
        f"Теперь можешь писать сообщение — оно уйдёт администратору."
    )

    try:
        if cb.message.caption:
            await cb.message.edit_caption(caption=final_text, reply_markup=kb_main())
        else:
            await cb.message.edit_text(final_text, reply_markup=kb_main())
    except Exception:
        await bot.send_message(uid, final_text, reply_markup=kb_main())
    await cb.answer()

# --- Антифлуд ---
def check_flood(user_id):
    flud = load_flud()
    now = time.time()
    uid = str(user_id)
    if uid not in flud:
        flud[uid] = []
    flud[uid] = [t for t in flud[uid] if now - t < 60]
    flud[uid].append(now)
    save_flud(flud)
    return len(flud[uid]) >= 10

# --- Сообщение от пользователя ---
@dp.message(F.chat.type == ChatType.PRIVATE)
async def user_message(message: Message):
    uid = message.from_user.id

    if uid == ADMIN_ID:
        if message.text and message.text.startswith("/"):
            await handle_admin_command(message)
        return

    if check_flood(uid):
        await message.answer("🚫 Слишком много сообщений. Подожди 3 минуты.")
        return

    db = load_db()
    if str(uid) not in db or not db[str(uid)].get("registered"):
        await message.answer("✧ Сначала выбери, что тебе нужно:", reply_markup=kb_topics())
        return

    if db[str(uid)].get("blocked"):
        await message.answer("🚫 Вы заблокированы. Обратитесь к администратору.")
        return

    topic_id = db[str(uid)].get("topic_id")
    if not topic_id:
        await message.answer("❋ Тема не найдена. Напиши /start заново.")
        return

    try:
        await bot.copy_message(
            chat_id=GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
        inc_incoming()
        db = load_db()
        db[str(uid)]["last_user_msg"] = time.time()
        save_db(db)
    except Exception as e:
        print(f"Ошибка копирования: {e}")

# --- Автоответ по таймеру ---
async def auto_reply_loop():
    while True:
        await asyncio.sleep(60)
        try:
            now = time.time()
            db = load_db()
            for uid, info in list(db.items()):
                if not info.get("registered") or info.get("blocked"):
                    continue
                topic_id = info.get("topic_id")
                last_user = info.get("last_user_msg", 0)
                last_auto = info.get("last_auto_reply", 0)
                if not topic_id or not last_user:
                    continue
                if last_auto >= last_user:
                    continue

                hour = datetime.now().hour
                is_night = hour >= 2 and hour < 9
                wait = 600 if is_night else 7200

                if now - last_user >= wait:
                    text = (
                        "🌙 Админы спят. Сладких снов! Утром обязательно ответим ♡"
                        if is_night
                        else "✧ Админ обязательно ответит, как только увидит. Подожди немного ♡"
                    )
                    try:
                        await bot.send_message(int(uid), text)
                        db[str(uid)]["last_auto_reply"] = now
                        save_db(db)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Автоответ ошибка: {e}")

# --- Автобэкап ---
async def backup_loop():
    while True:
        await asyncio.sleep(1800)
        try:
            if os.path.exists(DB_FILE):
                await bot.send_document(
                    ADMIN_ID,
                    FSInputFile(DB_FILE),
                    caption=f"✧ Автобэкап базы\n{datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
        except Exception as e:
            print(f"Бэкап ошибка: {e}")

# --- Команды админа (в личке) ---
async def handle_admin_command(message: Message):
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    db = load_db()

    if cmd == "/help":
        await message.answer(
            "✧ <b>Команды админа:</b>\n\n"
            "/stats — статистика\n"
            "/blocked — список заблокированных\n"
            "/find НОМЕР — найти по номеру\n"
            "/unban НОМЕР — разблокировать\n"
            "/broadcast текст — рассылка\n"
            "/help — эта справка"
        )
        return

    if cmd == "/stats":
        total = len([u for u in db.values() if u.get("registered")])
        blocked = sum(1 for v in db.values() if v.get("blocked"))
        s = load_stats()
        await message.answer(
            f"✧ <b>Статистика</b>\n\n"
            f"♡ Всего: <b>{total}</b>\n"
            f"✦ Чистых: <b>{total - blocked}</b>\n"
            f"🚫 Заблокированных: <b>{blocked}</b>\n\n"
            f"↓ Входящих: <b>{s.get('incoming', 0)}</b>\n"
            f"↑ Исходящих: <b>{s.get('outgoing', 0)}</b>"
        )
        return

    if cmd == "/blocked":
        bl = [(u, v) for u, v in db.items() if v.get("blocked")]
        if not bl:
            await message.answer("✦ Заблокированных нет.")
            return
        out = "🚫 <b>Заблокированные:</b>\n\n"
        for u, i in bl:
            out += f"• #{i.get('number', '?')} — ID <code>{u}</code>\n"
        out += "\nРазблокировать: <code>/unban НОМЕР</code>"
        await message.answer(out)
        return

    if cmd == "/find":
        if len(parts) < 2:
            await message.answer("Используй: /find НОМЕР"); return
        try: num = int(parts[1].strip().replace("#", ""))
        except: await message.answer("❋ Номер должен быть числом."); return
        uid, info = find_user_by_number(num)
        if not uid:
            await message.answer(f"❋ Пользователь #{num} не найден."); return
        await message.answer(
            f"✧ <b>Найден</b>\n\n"
            f"№ Номер: <b>#{num}</b>\n"
            f"ID: <code>{uid}</code>\n"
            f"Юзернейм: @{info.get('username', 'нет')}\n"
            f"✦ Тема: <b>{info.get('topic_name', '—')}</b>\n"
            f"♡ Хочет: <b>{info.get('gender', '—')}</b>\n"
            f"🚫 Блок: <b>{'Да' if info.get('blocked') else 'Нет'}</b>"
        )
        return

    if cmd == "/unban":
        if len(parts) < 2:
            await message.answer("Используй: /unban НОМЕР"); return
        try: num = int(parts[1].strip().replace("#", ""))
        except: await message.answer("❋ Номер должен быть числом."); return
        uid, info = find_user_by_number(num)
        if not uid:
            await message.answer(f"❋ Пользователь #{num} не найден."); return
        db[str(uid)]["blocked"] = False
        save_db(db)
        await message.answer(f"✦ Пользователь #{num} разблокирован.")
        return

    if cmd == "/broadcast":
        if len(parts) < 2:
            await message.answer("Используй: <code>/broadcast Текст</code>"); return
        bc_text = parts[1].strip()
        users = [u for u, v in db.items() if v.get("registered") and not v.get("blocked")]
        sent = 0; failed = 0
        status = await message.answer(f"↓ Отправляю... 0/{len(users)}")
        for i, u in enumerate(users, 1):
            try:
                await bot.send_message(int(u), f"✦ <b>Сообщение от админа:</b>\n\n{bc_text}")
                sent += 1
            except: failed += 1
            if i % 10 == 0:
                try: await status.edit_text(f"↓ Отправляю... {i}/{len(users)}")
                except: pass
            await asyncio.sleep(0.05)
        await status.edit_text(f"✦ <b>Готово</b>\n\nОтправлено: <b>{sent}</b>\nОшибок: <b>{failed}</b>")
        return

# --- Команды в группе (от ЛЮБОГО админа) ---
@dp.message(F.chat.id == GROUP_ID)
async def admin_group(message: Message):
    if not message.message_thread_id:
        return

    uid = find_user_by_topic(message.message_thread_id)
    if not uid:
        return

    text = (message.text or "").strip()

    if text == "/ban":
        db = load_db()
        if str(uid) in db:
            db[str(uid)]["blocked"] = True
            save_db(db)
            await message.reply(f"🚫 #{db[str(uid)].get('number','?')} заблокирован.")
            await log_action(f"🚫 Заблокирован #{db[str(uid)].get('number','?')}")
        return

    if text == "/unban":
        db = load_db()
        if str(uid) in db:
            db[str(uid)]["blocked"] = False
            save_db(db)
            await message.reply(f"✦ #{db[str(uid)].get('number','?')} разблокирован.")
        return

    if text.startswith("/"):
        return

    try:
        await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
        inc_outgoing()
    except Exception as e:
        err = str(e)
        if "blocked" in err.lower() or "forbidden" in err.lower():
            await message.reply("🔒 Пользователь заблокировал бота.")
            try:
                await bot.edit_forum_topic(
                    chat_id=GROUP_ID,
                    message_thread_id=message.message_thread_id,
                    name=f"🔒 Заблокировал бота"
                )
            except:
                pass
        print(f"Ошибка: {e}")

# --- Команда /reset для пользователя ---
@dp.message(F.chat.type == ChatType.PRIVATE, F.text == "/reset")
async def cmd_reset(message: Message):
    uid = message.from_user.id

    if uid == ADMIN_ID:
        await message.answer("✧ Админ не может сбросить себя.")
        return

    db = load_db()
    if str(uid) not in db:
        await message.answer("❋ Вас нет в базе. Напишите /start.")
        return

    old_number = db[str(uid)].get("number", "?")
    del db[str(uid)]
    save_db(db)

    await message.answer(
        "✧ Ваша регистрация сброшена.\n\n"
        f"№ Был номер: <b>#{old_number}</b>\n\n"
        "Напишите /start, чтобы зарегистрироваться заново и получить новую тему."
    )

# --- Запуск ---
def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Dummy server on port {port}")
        httpd.serve_forever()

async def main():
    threading.Thread(target=start_dummy_server, daemon=True).start()
    asyncio.create_task(auto_reply_loop())
    asyncio.create_task(backup_loop())
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
