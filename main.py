# multi_reactor.py
import os
import asyncio
import logging
import aiohttp
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

BOT_TOKENS = [t.strip() for t in os.environ["BOT_TOKENS"].split(",") if t.strip()]
if not BOT_TOKENS:
    raise SystemExit("Set BOT_TOKENS env var to a comma-separated list of bot tokens.")

# Comma-separated list of emojis, e.g. "🔥,❤️,😂,👏,👍,😎"
EMOJIS = [e.strip() for e in os.environ.get("EMOJIS", "🔥").split(",") if e.strip()]

PRIMARY_TOKEN = BOT_TOKENS[0]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

async def react_with_all_bots(chat_id: int, message_id: int):
    """Each bot reacts with its assigned emoji."""
    url_tpl = "https://api.telegram.org/bot{token}/setMessageReaction"

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, token in enumerate(BOT_TOKENS):
            emoji = EMOJIS[i % len(EMOJIS)]  # cycle through emoji list
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [{"type": "emoji", "emoji": emoji}],
                "is_big": False,
            }
            url = url_tpl.format(token=token)
            tasks.append(session.post(url, json=payload))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        ok = sum(1 for r in results if not isinstance(r, Exception) and (await r.json()).get("ok"))
        logging.info(f"Reactions sent: {ok}/{len(BOT_TOKENS)} with emojis {EMOJIS}")

async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    await react_with_all_bots(chat_id=msg.chat_id, message_id=msg.message_id)

def main():
    app = Application.builder().token(PRIMARY_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL & filters.UpdateType.CHANNEL_POST, on_channel_post))
    app.run_polling()

if __name__ == "__main__":
    main()
