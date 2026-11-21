import test from "node:test";
import assert from "node:assert/strict";
import { createComment, listCommentsByTask, commentsStore } from "../src/models/comment.js";

test("Comments: creates comment with valid payload", () => {
  commentsStore.length = 0;
  const comment = createComment({
    taskId: "tsk_101",
    authorId: "usr_alice",
    body: "Please review the database migration PR."
  });

  assert.ok(comment.id.startsWith("cmt_"));
  assert.equal(comment.taskId, "tsk_101");
  assert.equal(comment.authorId, "usr_alice");
  assert.equal(comment.body, "Please review the database migration PR.");
  assert.equal(comment.parentId, null);
  assert.ok(comment.createdAt);
});

test("Comments: creates threaded reply with parentId", () => {
  const reply = createComment({
    taskId: "tsk_101",
    authorId: "usr_bob",
    body: "Looks good to me!",
    parentId: "cmt_101"
  });

  assert.equal(reply.parentId, "cmt_101");
});

test("Comments: rejects empty body with VALIDATION_ERROR", () => {
  assert.throws(
    () => {
      createComment({
        taskId: "tsk_101",
        authorId: "usr_alice",
        body: "   "
      });
    },
    { code: "VALIDATION_ERROR" }
  );
});

test("Comments: lists comments scoped to specific task", () => {
  commentsStore.length = 0;
  createComment({ taskId: "tsk_A", authorId: "usr_1", body: "Task A comment" });
  createComment({ taskId: "tsk_B", authorId: "usr_2", body: "Task B comment" });

  const listA = listCommentsByTask("tsk_A");
  assert.equal(listA.length, 1);
  assert.equal(listA[0].body, "Task A comment");
});
