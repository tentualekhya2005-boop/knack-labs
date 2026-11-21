const MENTION_REGEX = /@([a-zA-Z0-9_.-]+)/g;

export function parseMentions(text) {
  if (!text || typeof text !== "string") {
    return [];
  }

  const mentions = [];
  let match;
  while ((match = MENTION_REGEX.exec(text)) !== null) {
    mentions.push({
      raw: match[0],
      username: match[1],
      position: {
        start: match.index,
        end: match.index + match[0].length
      }
    });
  }

  return mentions;
}

export function extractUniqueUsernames(text) {
  const parsed = parseMentions(text);
  return [...new Set(parsed.map((m) => m.username.toLowerCase()))];
}
