import os, logging
from typing import List
from dotenv import load_dotenv
from telegram import Update, ReactionTypeEmoji, ReactionTypeCustomEmoji
from telegram.ext import Application, ContextTypes, ChannelPostHandler, MessageHandler, filters

load_dotenv()
BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")
MODE        = os.getenv("MODE", "polling").lower()
EMOJIS      = [e.strip() for e in os.getenv("EMOJIS", "👍").split(",") if e.strip()]
CUSTOM_IDS  = [c.strip() for c in os.getenv("CUSTOM_EMOJI_IDS", "").split(",") if c.strip()]
PORT        = int(os.getenv("PORT", "3000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN is required in .env")

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.DEBUG)
log = logging.getLogger("reaction-bot")

def build_reactions():
    r = [ReactionTypeEmoji(e) for e in EMOJIS]
    r += [ReactionTypeCustomEmoji(custom_emoji_id=c) for c in CUSTOM_IDS]
    return r

def matches_target_channel(update: Update) -> bool:
    post = update.channel_post
    if not post: return False
    if CHANNEL_ID.startswith("@"):
        uname = post.chat.username
        return ("@" + uname) == CHANNEL_ID if uname else False
    return str(post.chat.id) == str(CHANNEL_ID)

async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    post = update.channel_post
    log.debug(f"channel_post chat_id={post.chat.id} msg_id={post.message_id} text={post.text!r}")
    if not matches_target_channel(update):
        log.debug(f"Not target channel (expected {CHANNEL_ID}), got {post.chat.id} / @{post.chat.username}")
        return
    reactions = build_reactions()
    if not reactions:
        log.warning("No reactions configured; skipping.")
        return
    try:
        await context.bot.set_message_reaction(
            chat_id=post.chat.id, message_id=post.message_id, reaction=reactions, is_big=False
        )
        log.info(f"Reacted to message_id={post.message_id} in chat_id={post.chat.id}")
    except Exception as e:
        log.error(f"Failed to react: {e}")

async def debug_log(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    # This logs ANY update type so you can see if Telegram is sending you things
    log.debug(f"DEBUG update: {update.to_dict()}")

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    # log everything (lowest priority)
    app.add_handler(MessageHandler(filters.ALL, debug_log), group=1_000_000)
    # handle channel posts
    app.add_handler(ChannelPostHandler(on_channel_post), group=0)

    if MODE == "webhook":
        if not WEBHOOK_URL: raise RuntimeError("WEBHOOK_URL is required when MODE=webhook")
        log.info(f"Starting webhook: {WEBHOOK_URL} (port {PORT})")
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path="", webhook_url=WEBHOOK_URL,
                        allowed_updates=["channel_post"])
    else:
        log.info("Starting polling…")
        app.run_polling(allowed_updates=["channel_post"], poll_interval=1.0)

if __name__ == "__main__":
    main()
