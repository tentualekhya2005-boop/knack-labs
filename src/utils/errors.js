export function sendErrorResponse(res, statusCode, code, message) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json");
  res.end(
    JSON.stringify({
      error: {
        code,
        message
      }
    })
  );
}
