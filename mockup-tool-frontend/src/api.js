const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const data = await response.json();
      detail = data?.detail?.message || JSON.stringify(data?.detail || data);
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
  downloadOutputs: () => `${API_BASE}/api/download/outputs`,
  downloadOutputFile: (filePath) => `${API_BASE}/api/download/output-file/${encodeURIComponent(filePath)}`,
  downloadOutputFolder: (folderName) => `${API_BASE}/api/download/output-folder/${encodeURIComponent(folderName)}`,
};
