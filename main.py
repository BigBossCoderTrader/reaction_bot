from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    emoji = "🔥"
    await context.bot.set_message_reaction(
        chat_id=msg.chat_id,
        message_id=msg.message_id,
        reaction=[ReactionTypeEmoji(emoji)]
    )

if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL & filters.UpdateType.CHANNEL_POST, on_channel_post))
    app.run_polling()
