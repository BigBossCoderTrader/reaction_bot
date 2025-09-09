import { Telegraf } from "telegraf";

// Your own pool (we'll intersect with what's allowed in the chat)
const PREFERRED = ["👍","❤️","🔥","🥰","👏","😁","🤔","🎉","💯","🤣","🙏","😍","👌","😎","🤩"];

const normalize = (e) => e === "❤" ? "❤️" : e; // normalize red heart

// cache allowed reactions per chat
const allowedCache = new Map();

/** Returns an array of standard emoji allowed in this chat, or null if all are allowed */
async function getAllowedEmoji(bot, chatId) {
  if (allowedCache.has(chatId)) return allowedCache.get(chatId);

  // Bot API: getChat -> ChatFullInfo may include available_reactions (list of ReactionType)
  const chat = await bot.telegram.callApi("getChat", { chat_id: chatId });
  const ar = chat.available_reactions; // may be omitted => all emoji allowed
  let allowed = null;

  if (Array.isArray(ar)) {
    // keep only standard emoji reactions (ignore custom emoji ids)
    allowed = ar
      .filter((r) => r.type === "emoji" && r.emoji)
      .map((r) => normalize(r.emoji));
  }

  allowedCache.set(chatId, allowed);
  return allowed;
}

export function setup(bot) {
  // IMPORTANT: channel posts come as 'channel_post', not 'message'
  bot.on("channel_post", async (ctx) => {
    try {
      const chatId = ctx.chat.id;
      const messageId = ctx.channelPost.message_id;

      // find a reaction that is allowed in this chat
      const allowed = await getAllowedEmoji(bot, chatId); // null => all allowed
      const pool = (allowed && allowed.length)
        ? PREFERRED.filter((e) => allowed.includes(normalize(e)))
        : PREFERRED;

      // fallback if intersection is empty
      const pick = (pool.length ? pool : ["👍"])[Math.floor(Math.random() * (pool.length || 1))];

      // Correct shape: reaction array + top-level is_big
      await ctx.telegram.callApi("setMessageReaction", {
        chat_id: chatId,
        message_id: messageId,
        reaction: [{ type: "emoji", emoji: normalize(pick) }],
        is_big: true
      });
    } catch (error) {
      console.error("Error setting reaction:", error);
    }
  });
}
