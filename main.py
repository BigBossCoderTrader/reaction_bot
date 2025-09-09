import os
import logging
from typing import List
from dotenv import load_dotenv
from telegram import Update, ReactionTypeEmoji, ReactionTypeCustomEmoji
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# ---------- Setup ----------
load_dotenv()
BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")
MODE        = os.getenv("MODE", "polling").lower()

EMOJIS      = [e.strip() for e in os.getenv("EMOJIS", "👍").split(",") if e.strip()]
CUSTOM_IDS  = [c.strip() for c in os.getenv("CUSTOM_EMOJI_IDS", "").split(",") if c.strip()]
PORT        = int(os.getenv("PORT", "3000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required in .env")

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
log = logging.getLogger("reaction-bot")


# ---------- Helpers ----------
def build_reactions() -> List:
    r = [ReactionTypeEmoji(e) for e in EMOJIS]
    r += [ReactionTypeCustomEmoji(custom_emoji_id=c) for c in CUSTOM_IDS]
    return r

def matches_target_channel(update: Update) -> bool:
    msg = update.effective_message
    if not msg:
        return False
    if CHANNEL_ID.startswith("@"):
        uname = msg.chat.username
        return ("@" + uname) == CHANNEL_ID if uname else False
    return str(msg.chat.id) == str(CHANNEL_ID)


# ---------- Handler ----------
async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not matches_target_channel(update):
        return
    reactions = build_reactions()
    try:
        await context.bot.set_message_reaction(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            reaction=reactions,
            is_big=False,
        )
        log.info("Reacted to message_id=%s in chat_id=%s", msg.message_id, msg.chat.id)
    except Exception as e:
        log.error("Failed to react: %s", e)


# ---------- Main ----------
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Catch new messages in channels
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, on_channel_post))

    if MODE == "webhook":
        if not WEBHOOK_URL:
            raise RuntimeError("WEBHOOK_URL is required when MODE=webhook")
        log.info("Starting webhook: %s (port %s)", WEBHOOK_URL, PORT)
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="",
            webhook_url=WEBHOOK_URL,
            allowed_updates=["channel_post"],
        )
    else:
        log.info("Starting polling…")
        app.run_polling(allowed_updates=["channel_post"], poll_interval=1.0)


if __name__ == "__main__":
    main()
