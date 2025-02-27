import os
import time
from telethon.sync import TelegramClient
from telethon.errors.rpcerrorlist import PeerIdInvalidError, SlowModeWaitError, SessionPasswordNeededError
from tinydb import TinyDB, Query
from datetime import datetime
import config

SESSIONS_DIR = "services/parser/bot_session"
CHATS_FILE = "services/parser/output.txt"
DB_FILE = "db.json"

if not os.path.exists("db"):
    os.makedirs("db")
db = TinyDB(DB_FILE)
settings = db.table("settings")
account = db.table("account")

if not settings.contains(Query().key == "message_delay"):
    settings.insert({"key": "message_delay", "value": 5})
if not settings.contains(Query().key == "cycle_delay"):
    settings.insert({"key": "cycle_delay", "value": 60})


def get_api_credentials():
    if not account.contains(Query().key == "api_id"):
        api_id = config.api_id
        api_hash = config.api_hash
        phone = config.PHONE_NUMBER
        account.insert({"key": "api_id", "value": api_id})
        account.insert({"key": "api_hash", "value": api_hash})
        account.insert({"key": "phone", "value": phone})
    else:
        api_id = account.get(Query().key == "api_id")["value"]
        api_hash = account.get(Query().key == "api_hash")["value"]
        phone = account.get(Query().key == "phone")["value"]

    return api_id, api_hash, phone


def create_session():
    api_id, api_hash, phone = get_api_credentials()
    session_name = f"{SESSIONS_DIR}/{phone}"
    client = TelegramClient(session_name, api_id, api_hash)

    client.connect()
    if not client.is_user_authorized():
        client.send_code_request(phone)
        code = input("Введите код из Telegram: ")
        try:
            client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Введите облачный пароль: ")
            client.sign_in(password=password)
        print("[INFO] Успешная авторизация!")
        account.upsert({"key": "authorized", "value": True}, Query().key == "authorized")
    client.disconnect()


def log_message(status, chat, message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{status}] Чат: {chat} | Сообщение: {message}")


def load_chats():
    if not os.path.exists(CHATS_FILE):
        print(f"[ERROR] Файл {CHATS_FILE} не найден.")
        return []
    with open(CHATS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def get_last_message(client):
    messages = client.get_messages("me", limit=1)
    return messages[0] if messages else None


def send_messages():
    if not os.path.exists(SESSIONS_DIR):
        print(f"[ERROR] Папка {SESSIONS_DIR} не найдена.")
        return

    api_id, api_hash, phone = get_api_credentials()
    session_path = f"{SESSIONS_DIR}/{phone}"

    chats = load_chats()
    if not chats:
        print("[ERROR] Файл chats.txt пуст.")
        return

    message_delay = settings.get(Query().key == "message_delay")["value"]
    cycle_delay = settings.get(Query().key == "cycle_delay")["value"]

    with TelegramClient(session_path, api_id, api_hash) as client:
        print(f"[INFO] Используется сессия: {phone}")
        message = get_last_message(client)
        if not message:
            print("[ERROR] Нет сообщений в Избранном для рассылки.")
            return

        while True:
            for chat in chats:
                try:
                    if message.text:
                        client.send_message(chat, message.text)
                        log_message("OK", chat, message.text)
                    if message.media:
                        client.send_file(chat, message.media, caption=message.text)
                        log_message("OK", chat, "[Медиафайл отправлен]")
                    time.sleep(message_delay)
                except SlowModeWaitError:
                    log_message("SLOWMODE", chat, "Пропущено из-за slowmode")
                    continue
                except PeerIdInvalidError:
                    log_message("ERROR", chat, "Чат недоступен")
                    continue
            print(f"[INFO] Цикл завершён. Ожидание {cycle_delay} секунд.")
            time.sleep(cycle_delay)


def configure_delays():
    while True:
        print("\n[1] Задержка между сообщениями")
        print("[2] Задержка между циклами")
        print("[3] Назад в главное меню")
        choice = input("Выберите действие: ")

        if choice == "1":
            new_delay = int(input("Введите новую задержку между сообщениями (в секундах): "))
            settings.update({"value": new_delay}, Query().key == "message_delay")
            print(f"[INFO] Задержка между сообщениями установлена: {new_delay} секунд")
        elif choice == "2":
            new_delay = int(input("Введите новую задержку между циклами (в секундах): "))
            settings.update({"value": new_delay}, Query().key == "cycle_delay")
            print(f"[INFO] Задержка между циклами установлена: {new_delay} секунд")
        elif choice == "3":
            break
        else:
            print("[ERROR] Неверный выбор.")


def authorize_again():
    phone = account.get(Query().key == "phone")["value"]
    session_path = f"{SESSIONS_DIR}/{phone}.session"

    account.remove(Query().key == "authorized")
    account.remove(Query().key == "api_id")
    account.remove(Query().key == "api_hash")
    account.remove(Query().key == "phone")

    if os.path.exists(session_path):
        os.remove(session_path)
        pass
    else:
        pass

    create_session()


def main_menu():
    while True:
        print("\n[1] Начать рассылку")
        print("[2] Настроить задержки")
        print("[3] Выход")
        print("[4] Авторизоваться заново")
        choice = input("Выберите действие: ")

        if choice == "1":
            send_messages()
        elif choice == "2":
            configure_delays()
        elif choice == "3":
            print("[INFO] Выход из программы.")
            break
        elif choice == "4":
            authorize_again()
        else:
            print("[ERROR] Неверный выбор.")


if __name__ == "__main__":
    if not account.contains(Query().key == "authorized"):
        create_session()
    main_menu()
