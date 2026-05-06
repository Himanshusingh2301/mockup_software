import { USER_ID_STORAGE_KEY } from "./workspaceUserId";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

let workspaceUserIdForRequests = "";

/** Hydrate from localStorage before any React effect runs (avoids race with initial /api/assets fetch). */
function readWorkspaceIdFromStorage() {
  try {
    const raw = localStorage.getItem(USER_ID_STORAGE_KEY);
    workspaceUserIdForRequests = raw?.trim() || "";
  } catch {
    workspaceUserIdForRequests = "";
  }
}

readWorkspaceIdFromStorage();

/** Call when the signed-in workspace user id changes (from App). */
export function setWorkspaceUserIdForApi(id) {
  workspaceUserIdForRequests = (id && String(id).trim()) || "";
}

/** Append workspace id for GETs that cannot send headers (img src, direct links). */
export function appendWorkspaceAuth(pathOrUrl) {
  const full = pathOrUrl.startsWith("http") ? pathOrUrl : `${API_BASE}${pathOrUrl}`;
  if (!workspaceUserIdForRequests) return full;
  const sep = full.includes("?") ? "&" : "?";
  return `${full}${sep}workspace_user_id=${encodeURIComponent(workspaceUserIdForRequests)}`;
}

async function request(path, options = {}) {
  const { skipWorkspaceHeader, ...rest } = options;
  const headers = new Headers(rest.headers);
  if (!skipWorkspaceHeader && workspaceUserIdForRequests && !headers.has("X-Workspace-User-Id")) {
    headers.set("X-Workspace-User-Id", workspaceUserIdForRequests);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...rest, headers });
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const data = await response.json();
      const d = data?.detail;
      if (typeof d === "string") detail = d;
      else detail = d?.message || JSON.stringify(d ?? data);
    } catch {
      // no-op
    }
    throw new Error(detail);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

export const apiBase = API_BASE;

export const api = {
  registerWorkspaceUser: (userId) =>
    request("/api/workspace/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
      skipWorkspaceHeader: true,
    }),
  loginWorkspaceUser: (userId) =>
    request("/api/workspace/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
      skipWorkspaceHeader: true,
    }),
  getAssets: () => request("/api/assets"),
  getTemplates: () => request("/api/templates"),
  saveTemplates: (templates) =>
    request("/api/templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templates }),
    }),
  uploadFiles: async (kind, files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    return request(`/api/upload/${kind}`, { method: "POST", body: formData });
  },
  uploadTempMockups: async (files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    return request("/api/upload-temp/mockups", { method: "POST", body: formData });
  },
  uploadTempInputs: async (files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    return request("/api/upload-temp/inputs", { method: "POST", body: formData });
  },
  deleteAsset: (kind, name) => request(`/api/assets/${kind}/${encodeURIComponent(name)}`, { method: "DELETE" }),
  deleteOutputFile: (filePath) => request(`/api/assets/outputs-file/${encodeURIComponent(filePath)}`, { method: "DELETE" }),
  deleteOutputFolder: (folderName) => request(`/api/outputs/folder/${encodeURIComponent(folderName)}`, { method: "DELETE" }),
  clearAssets: (kind) => request(`/api/assets/${kind}`, { method: "DELETE" }),
  renameAsset: (kind, name, newName) =>
    request(`/api/assets/${kind}/${encodeURIComponent(name)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_name: newName }),
    }),
  generate: (templates) =>
    request("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templates }),
    }),
  downloadOutputs: () => appendWorkspaceAuth("/api/download/outputs"),
  downloadOutputFile: (filePath) => appendWorkspaceAuth(`/api/download/output-file/${encodeURIComponent(filePath)}`),
  downloadOutputFolder: (folderName) => appendWorkspaceAuth(`/api/download/output-folder/${encodeURIComponent(folderName)}`),
};
