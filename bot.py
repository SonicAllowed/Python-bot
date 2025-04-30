import telebot
import random
import logging
import sys
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pathlib import Path
import os

# Настройка бота
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
OWNER_CHAT_ID = 7286174250  # Замените на ваш chat_id

# Настройка логирования
LOG_DIR = Path.home() / "telegram_bot_logs"
LOG_DIR.mkdir(exist_ok=True)

class UTF8FileHandler(logging.FileHandler):
    def __init__(self, filename, encoding='utf-8', mode='a'):
        super().__init__(filename, mode, encoding)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        UTF8FileHandler(LOG_DIR / 'bot_messages.log'),
        logging.StreamHandler()
    ]
)

# Глобальные переменные
message_map = {}
reply_states = {}

def log_message(direction: str, user_id: int, username: str, text: str):
    username = username or "no_username"
    logging.info(f"{direction} | UserID: {user_id} | Username: @{username} | Message: {text}")

def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🎲 Бросить кубик"),
        KeyboardButton("✉️ Написать админу")
    )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "Выберите действие:",
        reply_markup=create_main_keyboard()
    )
    log_message("INCOMING", message.chat.id, message.from_user.username, "/start command")

@bot.message_handler(func=lambda m: m.text == "🎲 Бросить кубик")
def dice_handler(message):
    sent_dice = bot.send_dice(message.chat.id, emoji="🎲")
    dice_value = sent_dice.dice.value
    bot.send_message(
        message.chat.id,
        f"🎲 Выпало: {dice_value}",
        reply_markup=create_main_keyboard()
    )
    log_message("DICE_ROLL", message.from_user.id, message.from_user.username, f"dice value: {dice_value}")

@bot.message_handler(func=lambda m: m.text == "✉️ Написать админу")
def contact_owner(message):
    bot.send_message(
        message.chat.id,
        "Напишите ваше сообщение для администратора:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("❌ Отмена"))
    )
    reply_states[message.chat.id] = "awaiting_message"

@bot.message_handler(func=lambda m: m.text == "❌ Отмена")
def cancel_handler(message):
    bot.send_message(
        message.chat.id,
        "Действие отменено",
        reply_markup=create_main_keyboard()
    )
    if message.chat.id in reply_states:
        del reply_states[message.chat.id]

@bot.message_handler(content_types=['text'])
def handle_messages(message):
    if message.chat.id in reply_states and reply_states[message.chat.id] == "awaiting_message":
        try:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✍️ Ответить", callback_data=f"reply_{message.chat.id}"))
            msg = bot.send_message(
                OWNER_CHAT_ID,
                f"📨 Сообщение от {message.from_user.first_name} (@{message.from_user.username or 'no_username'}):\n{message.text}",
                reply_markup=markup
            )
            message_map[msg.message_id] = message.chat.id
            bot.send_message(
                message.chat.id,
                "✉️ Ваше сообщение передано администратору!",
                reply_markup=create_main_keyboard()
            )
            del reply_states[message.chat.id]
        except Exception as e:
            logging.error(f"Ошибка пересылки: {e}")
        return

    if message.chat.id == OWNER_CHAT_ID and message.reply_to_message:
        original_msg_id = message.reply_to_message.message_id
        if original_msg_id in message_map:
            user_chat_id = message_map[original_msg_id]
            try:
                bot.send_message(
                    user_chat_id,
                    f"📩 Ответ администратора:\n{message.text}"
                )
                bot.send_message(
                    OWNER_CHAT_ID,
                    "✅ Ответ отправлен пользователю"
                )
                if OWNER_CHAT_ID in reply_states:
                    del reply_states[OWNER_CHAT_ID]
                del message_map[original_msg_id]
            except Exception as e:
                logging.error(f"Ошибка отправки ответа: {e}")
        return

    if message.chat.id == OWNER_CHAT_ID and OWNER_CHAT_ID in reply_states:
        user_chat_id = reply_states[OWNER_CHAT_ID]
        try:
            bot.send_message(
                user_chat_id,
                f"📩 Ответ администратора:\n{message.text}"
            )
            bot.send_message(
                OWNER_CHAT_ID,
                "✅ Ответ отправлен пользователю"
            )
            del reply_states[OWNER_CHAT_ID]
        except Exception as e:
            logging.error(f"Ошибка отправки ответа: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_"))
def reply_callback(call):
    user_chat_id = int(call.data.split("_")[1])
    reply_states[call.from_user.id] = user_chat_id
    bot.send_message(
        OWNER_CHAT_ID,
        "✏️ Введите ваш ответ (или ответьте на это сообщение):"
    )
    bot.answer_callback_query(call.id)

if __name__ == '__main__':
    logging.info("🤖 Бот запущен")
    logging.info(f"📁 Логи сохраняются в: {LOG_DIR}")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
