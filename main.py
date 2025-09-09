# multi_react.py
import os
import sys
import json
import httpx

TOKENS = [t.strip() for t in os.getenv("TOKENS", "").split(",") if t.strip()]
CHAT_ID = os.getenv("CHAT_ID")            # -100xxxxxxxxxxxx or @publicusername
MESSAGE_ID = os.getenv("MESSAGE_ID")      # numeric message id to react to
EMOJIS = [e.strip() for e in os.getenv("EMOJIS", "👍,❤️,🔥,😁,🎉,🙏,😍,🤣,😎,🤩").split(",") if e.strip()]
IS_BIG = os.getenv("IS_BIG", "false").lower() == "true"
MAX = int(os.getenv("MAX_REACTIONS", "10"))

def die(msg):
    print(msg, file=sys.stderr); sys.exit(1)

if not TOKENS: die("Set TOKENS=token1,token2,...")
if not CHAT_ID: die("Set CHAT_ID=-100... or @username")
if not MESSAGE_ID: die("Set MESSAGE_ID=123")

pick = EMOJIS[:MAX]  # you can randomize if you want
print(f"Using {len(pick)} emojis across {len(TOKENS)} bots.")

def set_reaction(token, chat_id, message_id, emoji, is_big=False):
    url = f"https://api.telegram.org/bot{token}/setMessageReaction"
    payload = {
        "chat_id": chat_id,
        "message_id": int(message_id),
        "reaction": [{"type": "emoji", "emoji": emoji}],
        "is_big": is_big
    }
    with httpx.Client(timeout=10) as c:
        r = c.post(url, json=payload)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "raw": r.text}
    return r.status_code, data

for i, emoji in enumerate(pick):
    token = TOKENS[i % len(TOKENS)]
    code, data = set_reaction(token, CHAT_ID, MESSAGE_ID, emoji, IS_BIG)
    ok = data.get("ok") if isinstance(data, dict) else False
    print(f"[{i+1}/{len(pick)}] {emoji} -> {code} | {json.dumps(data)[:200]}")
