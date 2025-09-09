import os
from dotenv import load_dotenv

from telegram import Update, ReactionTypeEmoji
from telegram.ext import (
    Application, ContextTypes,
    ChannelPostHandler
)

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")
EMOJI       = os.getenv("EMOJI", "👍")
MODE        = os.getenv("MODE", "polling").lower()
PORT        = int(os.getenv("PORT", "3000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # e.g., https://example.com/webhook

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """React to each new channel post with the configured emoji."""
    post = update.channel_post
    if not post:
        return

    # Only react in the target channel (accept numeric -100… or @username)
    if CHANNEL_ID and str(post.chat.id) != str(CHANNEL_ID) and str(post.chat.username and f"@{post.chat.username}") != str(CHANNEL_ID):
        return

    try:
        await context.bot.set_message_reaction(
            chat_id=post.chat.id,
            message_id=post.message_id,
            reaction=[ReactionTypeEmoji(EMOJI)],
            is_big=False,
        )
    except Exception as e:
        # Log to console; you could also send this to a log chat
        print(f"Failed to react to message {post.message_id}: {e}")

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # React to every new channel post
    app.add_handler(ChannelPostHandler(on_channel_post))

    if MODE == "webhook":
        if not WEBHOOK_URL:
            raise RuntimeError("WEBHOOK_URL is required in webhook mode")

        # Listen on /webhook path (PTB will set the webhook for you)
        print(f"Starting webhook on port {PORT}, url: {WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="",                 # empty path: PTB uses full WEBHOOK_URL as-is
            webhook_url=WEBHOOK_URL,
            allowed_updates=["channel_post"],
        )
    else:
        print("Starting polling (Ctrl+C to stop)…")
        app.run_polling(allowed_updates=["channel_post"])

if __name__ == "__main__":
    main()
