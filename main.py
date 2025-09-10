# multi_reactor.py
# pip install python-telegram-bot==21.4 aiohttp python-dotenv

import os
import asyncio
import logging
import json
import random
from typing import List, Optional

import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ---------- Config & setup ----------

load_dotenv()  # loads .env if present

def _get_env_list(name: str, default: str = "") -> List[str]:
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

BOT_TOKENS = _get_env_list("BOT_TOKENS")
if not BOT_TOKENS:
    raise SystemExit("❌ Set BOT_TOKENS in env or .env (comma-separated bot tokens).")

EMOJIS = _get_env_list("EMOJIS", "🔥")
EMOJI_MODE = os.getenv("EMOJI_MODE", "cycle").lower()  # cycle | random | same
IS_BIG = os.getenv("IS_BIG", "false").lower() in {"1", "true", "yes", "y"}
PER_BOT_DELAY_MS = int(os.getenv("PER_BOT_DELAY_MS", "0"))  # e.g., 100..300
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "15"))

PRIMARY_TOKEN = BOT_TOKENS[0]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

API_URL = "https://api.telegram.org/bot{token}/setMessageReaction"

# ---------- Helpers ----------

def pick_emoji_for_index(i: int) -> str:
    if EMOJI_MODE == "same":
        return EMOJIS[0]
    if EMOJI_MODE == "random":
        return random.choice(EMOJIS)
    # default: cycle
    return EMOJIS[i % len(EMOJIS)]

async def send_reaction(
    session: aiohttp.ClientSession,
    token: str,
    chat_id: int,
    message_id: int,
    emoji: str,
    is_big: bool
) -> bool:
    """Send one reaction with minimal 429 retry support."""
    url = API_URL.format(token=token)
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}],
        "is_big": is_big,
    }

    try:
        async with session.post(url, json=payload, timeout=HTTP_TIMEOUT) as resp:
            data = await resp.json(content_type=None)
            # Handle rate limit (Telegram may include retry_after)
            if not data.get("ok"):
                err = data.get("description", "")
                params = data.get("parameters") or {}
                retry_after = params.get("retry_after")
                if resp.status == 429 and retry_after:
                    logging.warning(f"429 for token ***... retrying in {retry_after}s (emoji={emoji})")
                    await asyncio.sleep(float(retry_after))
                    async with session.post(url, json=payload, timeout=HTTP_TIMEOUT) as resp2:
                        data2 = await resp2.json(content_type=None)
                        if data2.get("ok"):
                            return True
                        logging.warning(f"Bot error after retry: {data2}")
                        return False
                else:
                    logging.warning(f"Bot error: {json.dumps(data)}")
                    return False
            return True
    except asyncio.TimeoutError:
        logging.error("Timeout sending reaction")
        return False
    except aiohttp.ClientError as e:
        logging.error(f"HTTP error: {e}")
        return False
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        return False

async def react_with_all_bots(chat_id: int, message_id: int):
    """Each bot reacts once (emoji chosen by mode)."""
    timeout = aiohttp.ClientTimeout(total=None)
    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        results = []
        for i, token in enumerate(BOT_TOKENS):
            emoji = pick_emoji_for_index(i)
            if PER_BOT_DELAY_MS > 0 and i > 0:
                await asyncio.sleep(PER_BOT_DELAY_MS / 1000.0)
            ok = await send_reaction(session, token, chat_id, message_id, emoji, IS_BIG)
            results.append(ok)

        ok_count = sum(1 for r in results if r)
        logging.info(
            f"Reactions sent: {ok_count}/{len(BOT_TOKENS)} | mode={EMOJI_MODE} | is_big={IS_BIG} | emojis={EMOJIS}"
        )

# ---------- Telegram handlers ----------

async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg:
        return
    await react_with_all_bots(chat_id=msg.chat_id, message_id=msg.message_id)

def main():
    app = Application.builder().token(PRIMARY_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL & filters.UpdateType.CHANNEL_POST, on_channel_post))
    logging.info("✅ Reactor online. Waiting for channel posts…")
    logging.info(f"Config: bots={len(BOT_TOKENS)}, mode={EMOJI_MODE}, is_big={IS_BIG}, per_bot_delay_ms={PER_BOT_DELAY_MS}")
    app.run_polling()

if __name__ == "__main__":
    main()
