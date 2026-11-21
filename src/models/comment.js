import { randomUUID } from "node:crypto";

export const commentsStore = [];

export function validateCommentInput({ taskId, authorId, body, parentId = null }) {
  if (!taskId || typeof taskId !== "string" || !taskId.trim()) {
    const err = new Error("Invalid comment: taskId is required");
    err.code = "VALIDATION_ERROR";
    throw err;
  }
  if (!authorId || typeof authorId !== "string" || !authorId.trim()) {
    const err = new Error("Invalid comment: authorId is required");
    err.code = "VALIDATION_ERROR";
    throw err;
  }
  const trimmedBody = typeof body === "string" ? body.trim() : "";
  if (!trimmedBody || trimmedBody.length < 1 || trimmedBody.length > 5000) {
    const err = new Error("Invalid comment: body is required and must be between 1 and 5000 characters");
    err.code = "VALIDATION_ERROR";
    throw err;
  }

  return {
    taskId: taskId.trim(),
    authorId: authorId.trim(),
    body: trimmedBody,
    parentId: parentId && typeof parentId === "string" ? parentId.trim() : null
  };
}

export function createComment(data) {
  const validated = validateCommentInput(data);
  const now = new Date().toISOString();

  const comment = {
    id: `cmt_${randomUUID()}`,
    taskId: validated.taskId,
    authorId: validated.authorId,
    body: validated.body,
    parentId: validated.parentId,
    createdAt: now,
    updatedAt: now
  };

  commentsStore.push(comment);
  return comment;
}

export function listCommentsByTask(taskId) {
  if (!taskId) return [];
  return commentsStore.filter((c) => c.taskId === taskId);
}

export function findCommentById(id) {
  if (!id) return null;
  return commentsStore.find((c) => c.id === id) || null;
}
