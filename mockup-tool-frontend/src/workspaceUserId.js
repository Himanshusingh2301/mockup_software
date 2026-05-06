/** localStorage key for the workspace user id (scoped mockups / outputs). */
export const USER_ID_STORAGE_KEY = "mockgenerator_workspace_user_id";

/**
 * Normalize and validate an id for safe use as a single path segment later.
 * Returns { ok: true, value } or { ok: false, error }.
 */
export function validateWorkspaceUserId(raw) {
  const trimmed = String(raw ?? "").trim();
  if (!trimmed) {
    return { ok: false, error: "Enter a user ID." };
  }
  if (trimmed.length > 128) {
    return { ok: false, error: "User ID must be at most 128 characters." };
  }
  if (/[/\\]/.test(trimmed) || trimmed.includes("..")) {
    return { ok: false, error: 'User ID cannot contain "/", "\\", or "..".' };
  }
  return { ok: true, value: trimmed };
}

export function readStoredWorkspaceUserId() {
  try {
    const raw = localStorage.getItem(USER_ID_STORAGE_KEY);
    const v = raw?.trim();
    return v || "";
  } catch {
    return "";
  }
}

/** First visible character for avatar (handles many Unicode strings). */
export function avatarLetter(userId) {
  const s = String(userId ?? "").trim();
  if (!s) return "?";
  const first = [...s][0];
  return first ? first.toUpperCase() : "?";
}
