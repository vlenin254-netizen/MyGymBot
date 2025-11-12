import telebot
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import os
from telebot import types

TOKEN = "8554822217:AAHI2AJdlfbPbx8nZ_aewxMiaaiw7PcbIQU"  # твой токен
bot = telebot.TeleBot(TOKEN)

DB_PATH = "db.sqlite"
VIDEOS_DIR = "videos"

# --- Проверка папки для видео ---
if not os.path.exists(VIDEOS_DIR):
    os.makedirs(VIDEOS_DIR)

# --- Создание базы данных ---
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    day TEXT,
    type TEXT,
    video TEXT
)
''')
c.execute('''
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER,
    date TEXT,
    sets INTEGER,
    weight REAL,
    duration INTEGER
)
''')
conn.commit()
conn.close()

# --- Хранение состояния пользователя ---
user_state = {}

# --- Главная клавиатура ---
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🏋️ Силовая тренировка", "🏃 Кардио")
    markup.row("📅 Расписание", "➕ Добавить упражнение", "🗑 Удалить упражнение")
    markup.row("📈 Прогресс")
    return markup

# --- Хэлпер функции ---
def get_exercises_for_day(day):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, type, video FROM exercises WHERE day=?", (day,))
    exercises = c.fetchall()
    conn.close()
    return exercises

def save_progress(exercise_id, sets=None, weight=None, duration=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO progress (exercise_id, date, sets, weight, duration) VALUES (?,?,?,?,?)",
              (exercise_id, datetime.now().strftime("%Y-%m-%d"), sets, weight, duration))
    conn.commit()
    conn.close()

# --- Команды ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет, качок! 💪", reply_markup=main_keyboard())

# --- Тренировка на выбранный день ---
@bot.message_handler(func=lambda m: m.text in ["🏋️ Силовая тренировка","🏃 Кардио"])
def training_choice(message):
    day = datetime.now().strftime("%A").lower()
    exercises = get_exercises_for_day(day)
    if not exercises:
        bot.send_message(message.chat.id, f"Сегодня нет запланированных упражнений 😔", reply_markup=main_keyboard())
        return
    # фильтруем по типу
    ex_type = "strength" if message.text == "🏋️ Силовая тренировка" else "cardio"
    exercises = [e for e in exercises if e[2]==ex_type]
    if not exercises:
        bot.send_message(message.chat.id, f"Сегодня нет упражнений этого типа 😔", reply_markup=main_keyboard())
        return
    user_state[message.chat.id] = {"exercises": exercises, "index": 0}
    send_next_exercise(message.chat.id)

def send_next_exercise(chat_id):
    state = user_state.get(chat_id)
    if not state:
        return
    if state["index"] >= len(state["exercises"]):
        bot.send_message(chat_id, "Тренировка завершена! 🎉", reply_markup=main_keyboard())
        send_progress_graph(chat_id)
        user_state.pop(chat_id)
        return
    ex = state["exercises"][state["index"]]
    ex_id, name, ex_type, video = ex
    bot.send_message(chat_id, f"Упражнение: {name} ({'Силовое' if ex_type=='strength' else 'Кардио'})")
    if video and os.path.exists(video):
        bot.send_video(chat_id, open(video, 'rb'))
    if ex_type == "strength":
        msg = bot.send_message(chat_id, "Сколько подходов сделал?")
        bot.register_next_step_handler(msg, lambda m: ask_weight(m, ex_id))
    else:
        msg = bot.send_message(chat_id, "Сколько минут выполняли?")
        bot.register_next_step_handler(msg, lambda m: save_cardio(m, ex_id))

def ask_weight(message, ex_id):
    try:
        sets = int(message.text)
    except:
        sets = 0
    msg = bot.send_message(message.chat.id, "Какой вес использовал (кг)?")
    user_state[message.chat.id]["temp_sets"] = sets
    bot.register_next_step_handler(msg, lambda m: save_strength(m, ex_id))

def save_strength(message, ex_id):
    try:
        weight = float(message.text)
    except:
        weight = 0
    sets = user_state[message.chat.id].pop("temp_sets", 0)
    save_progress(ex_id, sets=sets, weight=weight)
    user_state[message.chat.id]["index"] += 1
    send_next_exercise(message.chat.id)

def save_cardio(message, ex_id):
    try:
        duration = int(message.text)
    except:
        duration = 0
    save_progress(ex_id, duration=duration)
    user_state[message.chat.id]["index"] += 1
    send_next_exercise(message.chat.id)

# --- Добавление упражнения ---
@bot.message_handler(func=lambda m: m.text=="➕ Добавить упражнение")
def add_exercise(message):
    msg = bot.send_message(message.chat.id, "Введите название упражнения:")
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    user_state[message.chat.id] = {"new_exercise": {"name": message.text}}
    msg = bot.send_message(message.chat.id, "Введите день недели (Понедельник…Воскресенье):")
    bot.register_next_step_handler(msg, process_day_step)

def process_day_step(message):
    user_state[message.chat.id]["new_exercise"]["day"] = message.text.lower()
    msg = bot.send_message(message.chat.id, "Выберите тип упражнения: Силовое или Кардио")
    bot.register_next_step_handler(msg, process_type_step)

def process_type_step(message):
    ex = user_state[message.chat.id]["new_exercise"]
    text = message.text.lower()
    if "сил" in text:
        ex["type"] = "strength"
    else:
        ex["type"] = "cardio"
    msg = bot.send_message(message.chat.id, "Если есть видео, отправьте его как файл, иначе напишите 'нет':")
    bot.register_next_step_handler(msg, process_video_step)

def process_video_step(message):
    ex = user_state[message.chat.id]["new_exercise"]
    if message.content_type == 'document':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        path = os.path.join(VIDEOS_DIR, message.document.file_name)
        with open(path, 'wb') as f:
            f.write(downloaded_file)
        ex["video"] = path
    else:
        ex["video"] = None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO exercises (name, day, type, video) VALUES (?,?,?,?)",
              (ex["name"], ex["day"], ex["type"], ex["video"]))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"Упражнение {ex['name']} добавлено! ✅", reply_markup=main_keyboard())
    user_state.pop(message.chat.id)

# --- Удаление упражнения ---
@bot.message_handler(func=lambda m: m.text=="🗑 Удалить упражнение")
def delete_exercise(message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, day FROM exercises ORDER BY day")
    exercises = c.fetchall()
    conn.close()
    if not exercises:
        bot.send_message(message.chat.id, "Список упражнений пустой.", reply_markup=main_keyboard())
        return
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for ex in exercises:
        markup.add(f"{ex[0]} - {ex[1]} ({ex[2].capitalize()})")
    msg = bot.send_message(message.chat.id, "Выберите упражнение для удаления:", reply_markup=markup)
    bot.register_next_step_handler(msg, confirm_delete)

def confirm_delete(message):
    try:
        ex_id = int(message.text.split(" - ")[0])
    except:
        bot.send_message(message.chat.id, "Ошибка выбора. Попробуй снова.", reply_markup=main_keyboard())
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM exercises WHERE id=?", (ex_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "Упражнение удалено ✅", reply_markup=main_keyboard())

# --- Просмотр расписания ---
@bot.message_handler(func=lambda m: m.text=="📅 Расписание")
def show_schedule(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for day in ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]:
        markup.add(day)
    msg = bot.send_message(message.chat.id, "Выберите день для просмотра упражнений:", reply_markup=markup)
    bot.register_next_step_handler(msg, show_day_exercises)

def show_day_exercises(message):
    day = message.text.lower()
    exercises = get_exercises_for_day(day)
    if not exercises:
        bot.send_message(message.chat.id, f"На {message.text} нет упражнений 😔", reply_markup=main_keyboard())
        return
    text = f"Упражнения на {message.text}:\n"
    for ex in exercises:
        text += f"- {ex[1]} ({'Силовое' if ex[2]=='strength' else 'Кардио'})\n"
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

# --- Прогресс и графики ---
@bot.message_handler(func=lambda m: m.text=="📈 Прогресс")
def progress(message):
    send_progress_graph(message.chat.id)

def send_progress_graph(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date, weight FROM progress WHERE weight IS NOT NULL ORDER BY date")
    data = c.fetchall()
    conn.close()
    if not data:
        bot.send_message(chat_id, "Нет данных для графиков.", reply_markup=main_keyboard())
        return
    dates = [d[0] for d in data]
    weights = [d[1] for d in data]
    plt.figure()
    plt.plot(dates, weights, marker='o')
    plt.title("Динамика веса")
    plt.xlabel("Дата")
    plt.ylabel("Вес (кг)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plot_file = "weight_plot.png"
    plt.savefig(plot_file)
    plt.close()
    bot.send_photo(chat_id, open(plot_file, 'rb'))

# --- Запуск бота ---
print("Бот запущен...")
bot.polling(none_stop=True)
