import { useEffect, useState } from "react";
import { setWorkspaceUserIdForApi } from "./api";
import WorkspaceUserIdModal from "./components/WorkspaceUserIdModal";
import MockupPositionTool from "./Tool/MockupPositionTool";
import { USER_ID_STORAGE_KEY } from "./workspaceUserId";

function readStoredUserId() {
  try {
    return localStorage.getItem(USER_ID_STORAGE_KEY)?.trim() || "";
  } catch {
    return "";
  }
}

function App() {
  const [workspaceUserId, setWorkspaceUserId] = useState(readStoredUserId);
  const [authModalKey, setAuthModalKey] = useState(0);

  useEffect(() => {
    setWorkspaceUserIdForApi(workspaceUserId);
  }, [workspaceUserId]);

  const handleSaveUserId = (id) => {
    localStorage.setItem(USER_ID_STORAGE_KEY, id);
    setWorkspaceUserIdForApi(id);
    setWorkspaceUserId(id);
  };

  const handleLogout = () => {
    try {
      localStorage.removeItem(USER_ID_STORAGE_KEY);
    } catch {
      // no-op
    }
    setWorkspaceUserIdForApi("");
    setWorkspaceUserId("");
    setAuthModalKey((k) => k + 1);
  };

  const needsUserId = !workspaceUserId;

  if (needsUserId) {
    return (
      <div className="min-h-screen bg-slate-100 text-slate-900">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4">
            <div>
              <h1 className="text-xl font-bold tracking-tight">Mock Generator Studio</h1>
              <p className="text-sm text-slate-500">Sign in with your user ID or create a new one below.</p>
            </div>
            <button
              type="button"
              className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
              onClick={() => document.getElementById("workspace-user-id")?.focus()}
            >
              Log in
            </button>
          </div>
        </header>
        <WorkspaceUserIdModal key={authModalKey} open onSave={handleSaveUserId} />
      </div>
    );
  }

  return <MockupPositionTool workspaceUserId={workspaceUserId} onLogout={handleLogout} />;
}

export default App;
