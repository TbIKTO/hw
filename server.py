"""
HolyWorld Telegram API Server
Читает сообщения от liteeventbot, парсит шахты, сортирует по времени.
"""
import os, json, asyncio, re, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("HW-API")

API_ID   = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION  = os.environ["TG_SESSION"]
BOT_USER = os.environ.get("TG_BOT", "liteeventbot")
API_KEY  = os.environ.get("API_KEY", "")
PORT     = int(os.environ.get("PORT", 8080))

# Хранилище: список {"name": "СолоЛайт #13", "seconds": 5, "display": "СолоЛайт #13 - 5с"}
_mines = []
_raw   = ""

def parse_mines(text: str) -> list:
    """
    Парсит текст сообщения бота.
    Формат строки: "СолоЛайт #13 - 5с" или "ДуоЛайт #38 - 0с"
    """
    mines = []
    for line in text.split("\n"):
        line = line.strip()
        # Убираем markdown символы ** и *
        line = line.replace("**", "").replace("*", "").strip()
        if not line:
            continue
        # Пробуем найти паттерн: ИмяРежима #Номер - Времяс
        # Например: "СолоЛайт #4 - 0с" или "ДуоЛайт #23 - 5с"
        m = re.match(r"(.+?)\s*#(\d+)\s*[-–]\s*(\d+)\s*[сc]", line, re.IGNORECASE)
        if m:
            name    = m.group(1).strip()
            number  = int(m.group(2))
            seconds = int(m.group(3))
            mines.append({
                "name":    name,
                "number":  number,
                "seconds": seconds,
                "display": f"{name} #{number} - {seconds}с"
            })
    return mines

def mines_to_lines(mines: list) -> list:
    """Конвертирует список шахт в строки для overlay, сортируя по времени."""
    if not mines:
        return ["§e[TG] Нет данных о шахтах"]

    # Сортируем по времени (ближайшие первые)
    sorted_mines = sorted(mines, key=lambda x: x["seconds"])

    lines = [f"§6§l⛏ Шахты HolyWorld", "§8──────────────────"]
    for mine in sorted_mines[:15]:  # max 15 строк
        sec = mine["seconds"]
        name = mine["name"]
        num  = mine["number"]
        # Цвет по времени
        if sec == 0:
            color = "§a"  # зелёный — прямо сейчас
        elif sec <= 30:
            color = "§e"  # жёлтый — скоро
        else:
            color = "§f"  # белый — далеко
        lines.append(f"{color}{name} §7#§e{num} §8- §f{sec}с")
    return lines

# ── HTTP сервер ───────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if API_KEY:
            if self.headers.get("X-API-Key", "") != API_KEY:
                self.send_response(403)
                self.end_headers()
                return

        lines = mines_to_lines(_mines)
        body  = json.dumps(lines, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args): pass

# ── Telegram ──────────────────────────────────────────────────────────────────
async def main():
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.start()
    log.info("Telegram авторизован!")

    async def refresh():
        global _mines, _raw
        try:
            entity   = await client.get_entity(BOT_USER)
            messages = await client.get_messages(entity, limit=5)
            for msg in messages:
                if msg.text and ("#" in msg.text or "Шахт" in msg.text):
                    _raw   = msg.text
                    _mines = parse_mines(msg.text)
                    log.info(f"Найдено {len(_mines)} шахт")
                    if _mines:
                        break
        except Exception as e:
            log.error(f"Ошибка: {e}")

    @client.on(events.NewMessage(from_users=BOT_USER))
    async def on_message(event):
        global _mines, _raw
        text = event.message.text or ""
        parsed = parse_mines(text)
        if parsed:
            _mines = parsed
            _raw   = text
            log.info(f"Новое сообщение: {len(parsed)} шахт")
        elif text.strip():
            # Сохраняем сырой текст для дебага
            _raw = text

    await refresh()
    log.info(f"Слушаю @{BOT_USER}...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), Handler).serve_forever(),
           daemon=True).start()
    log.info(f"HTTP на порту {PORT}")
    asyncio.run(main())
