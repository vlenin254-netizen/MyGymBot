import telebot
import json
import os
from flask import Flask, request
from threading import Thread

# Загружаем токен из переменных окружения
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DATA_FILE = "exercises.json"

# ---------- Работа с JSON ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "понедельник": [], "вторник": [], "среда": [],
                "четверг": [], "пятница": [], "суббота": [], "воскресенье": []
            }, f, ensure_ascii=False, indent=2)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data = load_data()

# ---------- Вспомогательные клавиатуры ----------
def cancel_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("↩️ Назад", "❌ Отмена")
    return kb


def days_keyboard():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("понедельник", "вторник", "среда")
    kb.row("четверг", "пятница", "суббота", "воскресенье")
    kb.row("❌ Отмена")
    return kb


# ---------- Команды ----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🏋️ Привет! Я твой фитнес-бот.\n\n"
                                      "Выбери день недели, чтобы добавить упражнение.",
                     reply_markup=days_keyboard())


@bot.message_handler(func=lambda m: m.text and m.text.lower() in data.keys())
def choose_day(message):
    day = message.text.lower()
    bot.send_message(message.chat.id, f"📆 Добавляем упражнение на {day}. Введи название упражнения:",
                     reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, lambda msg: get_exercise_name(msg, day))


def get_exercise_name(message, day):
    if message.text.lower() == "❌ отмена":
        return start(message)
    elif message.text.lower() == "↩️ назад":
        return start(message)

    name = message.text
    bot.send_message(message.chat.id, "💪 Это силовая тренировка? (да/нет)",
                     reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, lambda msg: get_exercise_type(msg, day, name))


def get_exercise_type(message, day, name):
    if message.text.lower() in ["❌ отмена", "↩️ назад"]:
        return choose_day(message)

    is_power = message.text.lower() in ["да", "д", "yes", "y"]
    bot.send_message(message.chat.id, "📹 Пришли видео упражнения (или напиши 'нет', чтобы пропустить):",
                     reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, lambda msg: get_video(msg, day, name, is_power))


def get_video(message, day, name, is_power):
    if message.text.lower() == "❌ отмена":
        return start(message)
    elif message.text.lower() == "↩️ назад":
        return get_exercise_name(message, day)

    video_id = None
    if message.content_type == "video":
        video_id = message.video.file_id
    elif message.text.lower() == "нет":
        video_id = None

    new_ex = {
        "название": name,
        "тип": "силовое" if is_power else "кардио",
        "video_id": video_id,
        "подходы": [],
        "вес": []
    }

    data[day].append(new_ex)
    save_data(data)

    if is_power:
        bot.send_message(message.chat.id, f"💪 Сколько подходов сделал в '{name}'?",
                         reply_markup=cancel_keyboard())
        bot.register_next_step_handler(message, lambda msg: get_sets(msg, day, name))
    else:
        bot.send_message(message.chat.id, f"🏃 Упражнение '{name}' добавлено как кардио!",
                         reply_markup=days_keyboard())


def get_sets(message, day, name):
    if message.text.lower() in ["❌ отмена", "↩️ назад"]:
        return get_video(message, day, name, True)

    try:
        sets = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Введите число.")
        return bot.register_next_step_handler(message, lambda msg: get_sets(msg, day, name))

    last = data[day][-1]
    last["подходы"].append(sets)
    save_data(data)

    bot.send_message(message.chat.id, "⚖️ Сколько кг было на последнем подходе?",
                     reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, lambda msg: get_weight(msg, day, name))


def get_weight(message, day, name):
    if message.text.lower() in ["❌ отмена", "↩️ назад"]:
        return get_sets(message, day, name)

    try:
        weight = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Введите число.")
        return bot.register_next_step_handler(message, lambda msg: get_weight(msg, day, name))

    last = data[day][-1]
    last["вес"].append(weight)
    save_data(data)

    bot.send_message(message.chat.id, "✅ Записано! Можно добавить новое упражнение.",
                     reply_markup=days_keyboard())


# ---------- Статистика ----------
@bot.message_handler(commands=['stats'])
def stats(message):
    msg = "📊 Твоя статистика:\n"
    for day, exs in data.items():
        msg += f"\n📅 {day.capitalize()}:\n"
        if not exs:
            msg += "  — Нет упражнений\n"
            continue
        for e in exs:
            msg += f"  🔸 {e['название']} ({e['тип']})\n"
            msg += f"     Подходы: {e['подходы']}  Вес: {e['вес']}\n"
    bot.send_message(message.chat.id, msg)


# ---------- Flask сервер для Render ----------
@app.route('/')
def home():
    return "Bot is running"


def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


# ---------- Запуск ----------
def run_bot():
    bot.polling(none_stop=True, interval=0, timeout=20)


if __name__ == "__main__":
    Thread(target=run_flask).start()
    Thread(target=run_bot).start()
