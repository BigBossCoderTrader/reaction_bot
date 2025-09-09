import os
import logging
from typing import List

from dotenv import load_dotenv
from telegram import Update, ReactionTypeEmoji, ReactionTypeCustomEmoji
from telegram.ext import Application, ContextTypes, ChannelPostHandler

# ---------- Setup ----------
load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")  # e.g., -100123... or @publicchannel
MODE        = os.getenv("MODE", "polling").lower()

# Reactions: standard emojis (comma-separated)
EMOJIS      = [e.strip() for e in os.getenv("EMOJIS", "👍").split(",") if e.strip()]
# Custom emoji IDs (comma-separated numeric strings). Leave empty if not used.
CUSTOM_IDS  = [c.strip() for c in os.getenv("CUSTOM_EMOJI_IDS", "").split(",") if c.strip()]

PORT        = int(os.getenv("PORT", "3000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # required only in webhook mode

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required in .env")

# Logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("reaction-bot")


# ---------- Helpers ----------
def build_reactions() -> List:
    """Create a list of ReactionType* objects from env config."""
    reactions = [ReactionTypeEmoji(e) for e in EMOJIS]
    reactions += [ReactionTypeCustomEmoji(custom_emoji_id=cid) for cid in CUSTOM_IDS]
    return reactions


def matches_target_channel(update: Update) -> bool:
    """Check if the channel_post belongs to the configured CHANNEL_ID."""
    post = update.channel_post
    if not post:
        return False

    if CHANNEL_ID.startswith("@"):  # for public channels
        username = post.chat.username
        return ("@" + username) == CHANNEL_ID if username else False
    else:  # for private channels (-100…)
        return str(post.chat.id) == str(CHANNEL_ID)


# ---------- Handlers ----------
async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """React to each new channel post with configured emojis."""
    post = update.channel_post
    if not post or not matches_target_channel(update):
        return

    reactions = build_reactions()
    if not reactions:
        log.warning("No reactions configured; skipping.")
        return

    try:
        await context.bot.set_message_reaction(
            chat_id=post.chat.id,
            message_id=post.message_id,
            reaction=reactions,   # multiple are allowed
            is_big=False,         # set True for big animated reaction
        )
        log.info("Reacted to message_id=%s in chat_id=%s", post.message_id, post.chat.id)
    except Exception as e:
        log.error("Failed to react to message_id=%s: %s", post.message_id, e)


# ---------- Main ----------
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(ChannelPostHandler(on_channel_post))

    if MODE == "webhook":
        if not WEBHOOK_URL:
            raise RuntimeError("WEBHOOK_URL is required when MODE=webhook")
        log.info("Starting webhook: %s (port %s)", WEBHOOK_URL, PORT)
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="",                 # full WEBHOOK_URL used
            webhook_url=WEBHOOK_URL,
            allowed_updates=["channel_post"],
        )
    else:
        log.info("Starting polling (Ctrl+C to stop)…")
        app.run_polling(allowed_updates=["channel_post"], poll_interval=1.0)


if __name__ == "__main__":
    main()
