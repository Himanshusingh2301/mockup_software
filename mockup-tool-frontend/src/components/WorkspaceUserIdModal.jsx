import { useId, useState } from "react";
import { api } from "../api";
import { validateWorkspaceUserId } from "../workspaceUserId";

/**
 * Modal: Log in with an existing ID or create a new workspace user ID.
 * Remount via parent `key` when a fresh empty form is needed (e.g. after logout).
 */
export default function WorkspaceUserIdModal({ open, onSave }) {
  const titleId = useId();
  const [mode, setMode] = useState("login"); // "login" | "create"
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  if (!open) return null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    const result = validateWorkspaceUserId(value);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError("");
    setIsSaving(true);
    try {
      if (mode === "login") {
        await api.loginWorkspaceUser(result.value);
      } else {
        await api.registerWorkspaceUser(result.value);
      }
      onSave(result.value);
    } catch (err) {
      setError(err.message || (mode === "login" ? "Could not log in." : "Could not create this user ID."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleGenerate = () => {
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `ws-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
    setValue(id);
    setError("");
  };

  const heading = mode === "login" ? "Log in" : "Create new user ID";
  const description =
    mode === "login"
      ? "Enter the user ID you registered before. It must match exactly what is stored on the server."
      : "Choose a unique ID for this workspace. It will be saved on the server and in this browser. You can also generate a random ID.";

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-900/20">
        <div className="mb-5 flex rounded-lg border border-slate-200 bg-slate-100 p-1">
          <button
            type="button"
            className={`flex-1 rounded-md px-3 py-2 text-sm font-semibold transition ${
              mode === "login"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Log in
          </button>
          <button
            type="button"
            className={`flex-1 rounded-md px-3 py-2 text-sm font-semibold transition ${
              mode === "create"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
            onClick={() => {
              setMode("create");
              setError("");
            }}
          >
            Create new ID
          </button>
        </div>

        <h2 id={titleId} className="text-lg font-bold tracking-tight text-slate-900">
          {heading}
        </h2>
        <p className="mt-2 text-sm text-slate-600">{description}</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="workspace-user-id" className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
              User ID
            </label>
            <input
              id="workspace-user-id"
              type="text"
              autoComplete="off"
              autoFocus
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setError("");
              }}
              placeholder={mode === "login" ? "Your registered user ID" : "e.g. alice-design or click Generate"}
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 font-mono text-sm text-slate-900 shadow-inner outline-none ring-slate-400 focus:border-[#4f7f81] focus:ring-2 focus:ring-[#a2c4c5]"
            />
            {error && (
              <p className="mt-2 text-sm font-medium text-red-600" role="alert">
                {error}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {mode === "create" && (
              <button
                type="button"
                disabled={isSaving}
                onClick={handleGenerate}
                className="rounded-lg border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-[0_3px_0_0_#cbd5e1] transition hover:bg-slate-100 active:translate-y-[2px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50"
              >
                Generate random ID
              </button>
            )}
            <button
              type="submit"
              disabled={isSaving}
              className="rounded-lg border border-[#3f6d6f] bg-[#2f6163] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_3px_0_0_#1a4345] transition hover:bg-[#275355] active:translate-y-[2px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSaving ? "Please wait…" : mode === "login" ? "Log in" : "Create & continue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
