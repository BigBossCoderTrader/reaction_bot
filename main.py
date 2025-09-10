# pip install python-telegram-bot==21.4
from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, ChannelPostHandler, ContextTypes
import os

BOT_TOKEN = os.environ["BOT_TOKEN"]  # put your token here or in env

async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    # choose your emoji (can be '👍', '🔥', '❤️', etc.)
    emoji = "🔥"
    # set ONE reaction on the new channel post
    await context.bot.set_message_reaction(
        chat_id=msg.chat_id,
        message_id=msg.message_id,
        reaction=[ReactionTypeEmoji(emoji)],
        is_big=False  # set True for big animation
    )

if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(ChannelPostHandler(on_channel_post))
    app.run_polling()
