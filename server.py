"""
HolyWorld Telegram API Server
Читает сообщения от liteeventbot, парсит шахты, сортирует по времени.
"""
import os, json, asyncio, re, logging, time
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
_last_update_time = 0.0
_raw   = ""

_pattern = re.compile(
    r'((?:Соло|Дуо|Трио|Клан)Лайт(?:\s*\([^)]+\))?)\s*#(\d+)\s*(?:[-–]\s*)?(\d+)\s*(?:сек|с|sec)',
    re.UNICODE | re.IGNORECASE
)

def parse_mines(text: str) -> list:
    """
    Парсит текст сообщения бота.
    Поддерживает различные форматы с и без дефиса, маркдауна и т.д.
    """
    mines = []
    clean_text = text.replace("**", "").replace("*", "").replace("`", "")
    for m in _pattern.finditer(clean_text):
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

def get_current_mines() -> list:
    """Возвращает актуальный список шахт с учетом прошедшего времени."""
    if not _mines:
        return []
    elapsed = int(time.time() - _last_update_time)
    updated_mines = []
    for m in _mines:
        m_copy = dict(m)
        m_copy["seconds"] = max(0, m_copy["seconds"] - elapsed)
        updated_mines.append(m_copy)
    return updated_mines

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

        lines = mines_to_lines(get_current_mines())
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

    async def fetch_snapshot():
        global _mines, _raw, _last_update_time
        try:
            entity = await client.get_entity(BOT_USER)
            prev_msgs = await client.get_messages(entity, limit=1)
            prev_id = prev_msgs[0].id if prev_msgs else 0

            await client.send_message(entity, "Снимок шахт")

            for _ in range(20):
                await asyncio.sleep(0.5)
                msgs = await client.get_messages(entity, limit=1)
                if msgs and msgs[0].id > prev_id and msgs[0].text:
                    parsed = parse_mines(msgs[0].text)
                    if parsed:
                        _mines = parsed
                        _raw = msgs[0].text
                        _last_update_time = time.time()
                        log.info(f"Найдено {len(_mines)} шахт")
                        return
                    else:
                        log.warning(f"Не удалось распарсить ответ бота: {msgs[0].text[:100]}...")
            log.warning("Бот не ответил на 'Снимок шахт' за 10 секунд")
        except Exception as e:
            log.error(f"Ошибка при запросе снимка: {e}")

    @client.on(events.NewMessage(from_users=BOT_USER))
    async def on_message(event):
        global _mines, _raw, _last_update_time
        text = event.message.text or ""
        parsed = parse_mines(text)
        if parsed:
            _mines = parsed
            _raw   = text
            _last_update_time = time.time()
            log.info(f"Новое сообщение: {len(parsed)} шахт")
        elif text.strip():
            _raw = text
            log.info(f"Получено сообщение (не распаршено): {text[:100]}...")

    await fetch_snapshot()
    log.info(f"Слушаю @{BOT_USER}...")

    async def auto_refresh_loop():
        while True:
            await asyncio.sleep(25)
            await fetch_snapshot()

    asyncio.ensure_future(auto_refresh_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), Handler).serve_forever(),
           daemon=True).start()
    log.info(f"HTTP на порту {PORT}")
    asyncio.run(main())

