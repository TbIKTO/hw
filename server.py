"""
HolyWorld Telegram API Server
Деплоится на Railway, читает сообщения от бота с твоего аккаунта,
отдаёт их через HTTP API.

Переменные окружения Railway:
  TG_API_ID     — api_id с my.telegram.org
  TG_API_HASH   — api_hash с my.telegram.org
  TG_SESSION    — base64 строка сессии (получить через get_session.py)
  TG_BOT        — username бота без @
  API_KEY       — секретный ключ для защиты API (придумай сам)
  PORT          — порт (Railway ставит автоматически)
"""
import os, json, asyncio, base64, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("HW-API")

# ── Конфиг из переменных окружения ──────────────────────────────────────────
API_ID   = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION  = os.environ["TG_SESSION"]   # StringSession строка
BOT_USER = os.environ.get("TG_BOT", "liteeventbot")
API_KEY  = os.environ.get("API_KEY", "")
PORT     = int(os.environ.get("PORT", 8080))

# ── Хранилище данных ─────────────────────────────────────────────────────────
_data = {"lines": ["§e[TG] Загрузка..."], "raw": ""}

def set_data(lines, raw=""):
    _data["lines"] = lines
    _data["raw"]   = raw

# ── HTTP сервер ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Проверка API ключа
        if API_KEY:
            token = self.headers.get("X-API-Key", "")
            if token != API_KEY:
                self.send_response(403)
                self.end_headers()
                return

        body = json.dumps(_data["lines"], ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args): pass

def start_http():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info(f"HTTP сервер запущен на порту {PORT}")
    server.serve_forever()

# ── Telegram ─────────────────────────────────────────────────────────────────
async def main():
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.start()
    log.info("Telegram авторизован!")

    async def refresh():
        try:
            entity   = await client.get_entity(BOT_USER)
            messages = await client.get_messages(entity, limit=20)
            lines    = [f"§6§l⛏ @{BOT_USER}", "§8──────────────────"]
            raw_text = ""
            for msg in reversed(messages):
                if not msg.text: continue
                raw_text = msg.text
                for line in msg.text.split("\n"):
                    line = line.strip()
                    if not line: continue
                    if len(line) > 32: line = line[:30] + ".."
                    lines.append("§f" + line)
            if len(lines) <= 2:
                lines.append("§7Нет сообщений")
            set_data(lines, raw_text)
            log.info(f"Обновлено: {len(lines)} строк")
        except Exception as e:
            log.error(f"Ошибка: {e}")
            set_data(["§c[TG] Ошибка:", f"§7{str(e)[:28]}"])

    @client.on(events.NewMessage(from_users=BOT_USER))
    async def on_message(event):
        log.info("Новое сообщение от бота")
        await refresh()

    await refresh()
    log.info(f"Слушаю @{BOT_USER}...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    # HTTP в отдельном потоке
    Thread(target=start_http, daemon=True).start()
    asyncio.run(main())
