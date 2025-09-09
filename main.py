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
EMOJIS      = [e.strip() for e in os.getenv("EMOJIS", "👍,🔥,😀").split(",") if e.strip()]
CUSTOM_IDS  = [c.strip() for c in os.getenv("CUSTOM_EMOJI_IDS", "").split(",") if c.strip()]

# How many reactions to set per message (Telegram may still limit per actor)
MAX_REACTIONS = max(1, int(os.getenv("MAX_REACTIONS", "3")))

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

def matches_target_channel(update: Update) -> bool:
    msg = update.effective_message
    if not msg:
        return False
    if CHANNEL_ID.startswith("@"):
        uname = msg.chat.username
        return ("@" + uname) == CHANNEL_ID if uname else False
    return str(msg.chat.id) == str(CHANNEL_ID)

def is_reactable(msg) -> bool:
    # Skip service/automatic/system posts
    if getattr(msg, "is_automatic_forward", False):
        return False
    if getattr(msg, "pinned_message", None):
        return False  # pin event, not real content
    # Consider “real” content
    return any([
        bool(getattr(msg, "text", None)),
        bool(getattr(msg, "caption", None)),
        bool(getattr(msg, "photo", None)),
        bool(getattr(msg, "video", None)),
        bool(getattr(msg, "animation", None)),
        bool(getattr(msg, "document", None)),
        bool(getattr(msg, "audio", None)),
        bool(getattr(msg, "voice", None)),
        bool(getattr(msg, "video_note", None)),
        bool(getattr(msg, "sticker", None)),
        bool(getattr(msg, "poll", None)),
    ])

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
        # r may be ReactionTypeEmoji or ReactionTypeCustomEmoji
        if hasattr(r, "emoji") and r.emoji:
            std.add(normalize_emoji(r.emoji))
        elif hasattr(r, "custom_emoji_id") and r.custom_emoji_id:
            custom.add(r.custom_emoji_id)

    data = {"std": std, "custom": custom}
    allowed_cache[chat_id] = data
    return data

def unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

async def pick_allowed_reactions(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    k: int
) -> List[Any]:
    """
    Build up to k allowed ReactionType* for this chat:
      1) Use intersection of EMOJIS ∩ allowed standard
      2) If not enough, add other allowed standard
      3) If still short, add allowed custom emoji ids from CUSTOM_IDS
    """
    allowed = await get_allowed_for_chat(context, chat_id)

    # Preferred list normalized & unique
    preferred_std = unique_preserve_order([normalize_emoji(e) for e in EMOJIS])

    if allowed is None:
        # All allowed; take up to k from preferred list (randomized)
        pool = preferred_std[:]
        random.shuffle(pool)
        chosen = pool[:k]
        return [ReactionTypeEmoji(e) for e in chosen]

    std_allowed = list(allowed.get("std", set()))
    custom_allowed = list(allowed.get("custom", set()))

    # 1) Intersection with preferred
    intersect = [e for e in preferred_std if e in allowed.get("std", set())]
    random.shuffle(intersect)

    chosen: List[Any] = [ReactionTypeEmoji(e) for e in intersect[:k]]

    # 2) Fill with other allowed standard
    if len(chosen) < k and std_allowed:
        extra_std = [e for e in std_allowed if e not in [rt.emoji for rt in chosen if hasattr(rt, "emoji")]]
        random.shuffle(extra_std)
        for e in extra_std:
            if len(chosen) >= k:
                break
            chosen.append(ReactionTypeEmoji(e))

    # 3) Fill with allowed custom ids from CUSTOM_IDS
    if len(chosen) < k and custom_allowed and CUSTOM_IDS:
        usable_custom = [cid for cid in CUSTOM_IDS if cid in custom_allowed]
        random.shuffle(usable_custom)
        for cid in usable_custom:
            if len(chosen) >= k:
                break
            chosen.append(ReactionTypeCustomEmoji(custom_emoji_id=cid))

    return chosen[:k]

# -------- Handler --------
async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not matches_target_channel(update):
        return
    if not is_reactable(msg):
        return

    # Try multiple reactions
    reactions = await pick_allowed_reactions(context, msg.chat.id, MAX_REACTIONS)
    if not reactions:
        log.warning("No allowed reactions found for chat %s; skipping.", msg.chat.id)
        return

    try:
        await context.bot.set_message_reaction(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            reaction=reactions,
            is_big=False,  # True for big animation
        )
        log.info("Reacted (x%s) to message_id=%s in chat_id=%s", len(reactions), msg.message_id, msg.chat.id)
    except Exception as e:
        # Fallback: try just one (some chats limit per-actor to one)
        log.warning("Multi-reaction failed (%s). Falling back to single.", e)
        try:
            await context.bot.set_message_reaction(
                chat_id=msg.chat.id,
                message_id=msg.message_id,
                reaction=[reactions[0]],
                is_big=False,
            )
            log.info("Reacted (fallback single) to message_id=%s in chat_id=%s", msg.message_id, msg.chat.id)
        except Exception as e2:
            log.error("Failed to react even with single: %s", e2)

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # Channel posts come as messages in channel chats
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
