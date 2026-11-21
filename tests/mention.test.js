import test from "node:test";
import assert from "node:assert/strict";
import { parseMentions, extractUniqueUsernames } from "../src/utils/mention_parser.js";

test("MentionParser: parses single and multiple mentions from text", () => {
  const text = "Hey @alice and @bob.builder, can you check with @charlie-ops?";
  const mentions = parseMentions(text);

  assert.equal(mentions.length, 3);
  assert.equal(mentions[0].username, "alice");
  assert.equal(mentions[0].raw, "@alice");
  assert.equal(mentions[1].username, "bob.builder");
  assert.equal(mentions[2].username, "charlie-ops");
});

test("MentionParser: returns empty array for text with no mentions", () => {
  const mentions = parseMentions("No mentions here whatsoever.");
  assert.equal(mentions.length, 0);
});

test("MentionParser: extractUniqueUsernames returns deduplicated lowercased handles", () => {
  const text = "@Alice pinged @BOB and @alice again!";
  const unique = extractUniqueUsernames(text);

  assert.equal(unique.length, 2);
  assert.deepEqual(unique.sort(), ["alice", "bob"]);
});
