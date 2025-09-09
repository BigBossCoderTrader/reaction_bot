import os
import logging
import random
from typing import List, Optional, Set, Dict, Any

from dotenv import load_dotenv
from telegram import (
    Update,
    ReactionTypeEmoji,
    ReactionTypeCustomEmoji,
    Chat,
)
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# -------- Setup --------
load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("CHANNEL_ID", "")   # -100... or @publicusername
MODE        = os.getenv("MODE", "polling").lower()

# Your preferred emojis; we’ll intersect with what the channel allows
EMOJIS      = [e.strip() for e in os.getenv("EMOJIS", "👍").split(",") if e.strip()]
CUSTOM_IDS  = [c.strip() for c in os.getenv("CUSTOM_EMOJI_IDS", "").split(",") if c.strip()]

PORT        = int(os.getenv("PORT", "3000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required in .env")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("reaction-bot")

# Cache of allowed reactions per chat_id
# None => all emojis allowed
AllowedCache = Dict[int, Optional[Dict[str, Set[str]]]]
allowed_cache: AllowedCache = {}

def normalize_emoji(e: str) -> str:
    # Normalize red heart forms
    return "❤️" if e == "❤" else e

def build_reactions_list(emojis: List[str]) -> List[ReactionTypeEmoji]:
    return [ReactionTypeEmoji(normalize_emoji(e)) for e in emojis]

def matches_target_channel(update: Update) -> bool:
    msg = update.effective_message
    if not msg:
        return False
    if CHANNEL_ID.startswith("@"):
        uname = msg.chat.username
        return ("@" + uname) == CHANNEL_ID if uname else False
    return str(msg.chat.id) == str(CHANNEL_ID)

async def get_allowed_for_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> Optional[Dict[str, Set[str]]]:
    """
    Returns:
      None => all emojis allowed in this chat
      dict with keys:
        'std' -> set of allowed standard emoji strings
        'custom' -> set of allowed custom emoji IDs
    """
    if chat_id in allowed_cache:
        return allowed_cache[chat_id]

    chat: Chat = await context.bot.get_chat(chat_id)
    ar = getattr(chat, "available_reactions", None)

    if not ar:
        allowed_cache[chat_id] = None  # all allowed
        return None

    std: Set[str] = set()
    custom: Set[str] = set()

    # ar may be ChatAvailableReactionsSome with .reactions,
    # or ChatAvailableReactionsAll (no list => all allowed)
    reactions = getattr(ar, "reactions", None)
    if reactions is None:
        allowed_cache[chat_id] = None  # all allowed
        return None

    for r in reactions:
        if isinstance(r, ReactionTypeEmoji) and getattr(r, "emoji", None):
            std.add(normalize_emoji(r.emoji))
        elif isinstance(r, ReactionTypeCustomEmoji) and getattr(r, "custom_emoji_id", None):
            custom.add(r.custom_emoji_id)

    data = {"std": std, "custom": custom}
    allowed_cache[chat_id] = data
    return data

async def pick_allowed_emoji(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> Optional[Any]:
    """
    Pick one allowed reaction for this chat:
      - Prefer intersection of EMOJIS ∩ allowed standard emojis
      - Else any allowed standard emoji
      - Else try a custom emoji from CUSTOM_IDS that’s allowed
    Returns a ReactionTypeEmoji or ReactionTypeCustomEmoji, or None.
    """
    allowed = await get_allowed_for_chat(context, chat_id)

    # All allowed: pick from your preferred list
    if allowed is None:
        return ReactionTypeEmoji(normalize_emoji(random.choice(EMOJIS)))

    std_allowed = list(allowed.get("std", set()))
    custom_allowed = list(allowed.get("custom", set()))

    # Intersect preferred with allowed standard
    preferred_std = [e for e in EMOJIS if normalize_emoji(e) in allowed.get("std", set())]
    if preferred_std:
        return ReactionTypeEmoji(normalize_emoji(random.choice(preferred_std)))

    # If no intersection, but some standard allowed, pick one of those
    if std_allowed:
        return ReactionTypeEmoji(random.choice(std_allowed))

    # If only custom emojis are allowed & you provided IDs, try those
    usable_custom = [cid for cid in CUSTOM_IDS if cid in custom_allowed]
    if usable_custom:
        return ReactionTypeCustomEmoji(custom_emoji_id=random.choice(usable_custom))

    # Nothing usable
    return None

# -------- Handler --------
async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not matches_target_channel(update):
        return

    reaction_type = await pick_allowed_emoji(context, msg.chat.id)
    if reaction_type is None:
        log.warning("No allowed reaction found for chat %s; skipping.", msg.chat.id)
        return

    try:
        # Send ONE reaction (bots typically can set one reaction per message)
        await context.bot.set_message_reaction(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            reaction=[reaction_type],
            is_big=False,  # set True if you want the big animation
        )
        log.info("Reacted to message_id=%s in chat_id=%s", msg.message_id, msg.chat.id)
    except Exception as e:
        log.error("Failed to react: %s", e)

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Channel posts come as channel messages; this filter captures them
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
