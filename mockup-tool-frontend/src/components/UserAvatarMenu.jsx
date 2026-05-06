import { useEffect, useRef, useState } from "react";
import { FiChevronDown, FiLogOut } from "react-icons/fi";
import { avatarLetter } from "../workspaceUserId";

export default function UserAvatarMenu({ workspaceUserId, onLogout }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const letter = avatarLetter(workspaceUserId);

  useEffect(() => {
    function handlePointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        title={workspaceUserId ? `Account — ${workspaceUserId}` : "Open account menu"}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="Account menu"
        onClick={() => setOpen((prev) => !prev)}
        className={[
          "group relative flex cursor-pointer items-center gap-1 rounded-full border bg-white py-1 pl-1 pr-2 shadow-[0_4px_14px_-4px_rgba(15,23,42,0.18)] transition-all duration-200",
          "border-slate-200/90 hover:-translate-y-0.5 hover:border-[#3f6d6f]/45 hover:shadow-[0_12px_28px_-8px_rgba(47,97,99,0.35)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4f7f81] focus-visible:ring-offset-2",
          open ? "border-[#3f6d6f]/50 shadow-[0_12px_28px_-8px_rgba(47,97,99,0.35)] ring-1 ring-[#4f7f81]/25" : "",
        ].join(" ")}
      >
        <span
          className={[
            "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#2f6163] via-[#3d7274] to-[#4f7f81] text-[13px] font-bold tracking-tight text-white",
            "shadow-inner shadow-black/10 ring-2 ring-white/25 transition-transform duration-200",
            "group-hover:scale-[1.03] group-hover:shadow-[0_4px_12px_-2px_rgba(47,97,99,0.55)]",
            open ? "scale-[1.03] ring-white/40" : "",
          ].join(" ")}
        >
          {letter}
        </span>
        <FiChevronDown
          size={16}
          strokeWidth={2.5}
          className={`shrink-0 text-slate-500 transition-transform duration-200 group-hover:text-[#2f6163] ${open ? "rotate-180 text-[#2f6163]" : ""}`}
          aria-hidden
        />
      </button>

      {open ? (
        <div
          className="absolute right-0 z-[150] mt-2 min-w-[14.5rem] origin-top-right overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-[0_22px_50px_-12px_rgba(15,23,42,0.28)] ring-1 ring-black/5"
          role="menu"
        >
          <div className="bg-gradient-to-b from-slate-50/90 to-white px-3.5 py-3">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Signed in as</p>
            <p
              className="mt-1 truncate font-mono text-[13px] font-semibold text-slate-800"
              title={workspaceUserId}
            >
              {workspaceUserId}
            </p>
          </div>
          <div className="border-t border-slate-100 p-1.5">
            <button
              type="button"
              role="menuitem"
              className="flex w-full cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-red-600 transition-colors hover:bg-red-50 active:bg-red-100/80"
              onClick={() => {
                setOpen(false);
                onLogout?.();
              }}
            >
              <FiLogOut size={17} className="shrink-0 opacity-90" aria-hidden />
              Log out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
