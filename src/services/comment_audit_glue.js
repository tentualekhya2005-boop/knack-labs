import { recordAuditEvent } from "../models/audit_log.js";

export function wireCommentAuditEvents(eventEmitter) {
  if (!eventEmitter || typeof eventEmitter.on !== "function") {
    throw new Error("Invalid eventEmitter: must support .on() subscription");
  }

  const handlers = [
    {
      event: "comment.created",
      map: (data) => ({
        teamId: data.teamId,
        action: "comment.created",
        actorId: data.authorId,
        details: {
          resourceType: "comment",
          resourceId: data.commentId,
          taskId: data.taskId
        }
      })
    },
    {
      event: "comment.updated",
      map: (data) => ({
        teamId: data.teamId,
        action: "comment.updated",
        actorId: data.authorId,
        details: {
          resourceType: "comment",
          resourceId: data.commentId,
          taskId: data.taskId
        }
      })
    },
    {
      event: "comment.deleted",
      map: (data) => ({
        teamId: data.teamId,
        action: "comment.deleted",
        actorId: data.authorId,
        details: {
          resourceType: "comment",
          resourceId: data.commentId,
          taskId: data.taskId
        }
      })
    }
  ];

  for (const { event, map } of handlers) {
    eventEmitter.on(event, (data) => {
      const payload = map(data);
      recordAuditEvent(payload);
    });
  }

  return () => {
    for (const { event } of handlers) {
      eventEmitter.removeAllListeners(event);
    }
  };
}
