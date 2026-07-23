"""
Запусти этот скрипт ОДИН РАЗ локально чтобы получить строку сессии.
Полученную строку вставь в переменную TG_SESSION на Railway.

Запуск: python get_session.py
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID   = input("Введи api_id: ").strip()
API_HASH = input("Введи api_hash: ").strip()
PHONE    = input("Введи номер телефона (+7...): ").strip()

with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
    client.start(phone=PHONE)
    session_str = client.session.save()
    print("\n" + "="*60)
    print("ТВОЯ СТРОКА СЕССИИ (вставь в TG_SESSION на Railway):")
    print("="*60)
    print(session_str)
    print("="*60)
