import { useEffect, useMemo, useState } from "react";
import { FiTrash2 } from "react-icons/fi";
import { api, apiBase } from "../api";

const USE_CASES = [
  {
    id: "simple",
    name: "Simple",
  },
  {
    id: "overlay",
    name: "Overlay",
  },
];

const BACKEND_TEMPLATE_KEYS = [
  "id",
  "template_path",
  "mode",
  "card_geometry",
  "fit",
  "cover_anchor",
  "white_threshold",
  "mask_expand_px",
  "mask_feather_px",
  "white_mask_feather_px",
  "white_mask_erode_iters",
  "paper_edge_blend_min_alpha",
  "mask_align_quad_x",
  "mask_align_use_centroid",
  "mask_align_flip_x",
  "cover_offset_x",
  "cover_offset_y",
  "render_scale",
  "paper_edge_blend",
];

const SELECT_FIELD_OPTIONS = {
  mode: ["simple", "overlay"],
  card_geometry: ["quad", "axis_rect"],
  fit: ["contain", "cover"],
  cover_anchor: ["center", "top", "bottom"],
};

const DEFAULT_TEMPLATES = [
  {
    id: "overlay_hands_example",
    template_path: "mockups/01.png",
    mode: "overlay",
    card_geometry: "quad",
    fit: "cover",
    cover_anchor: "center",
    white_threshold: 240,
    mask_expand_px: 2,
    mask_feather_px: 0.8,
    white_mask_feather_px: 0.8,
    white_mask_erode_iters: 0,
    paper_edge_blend: true,
    paper_edge_blend_min_alpha: 0.00392156862745098,
    mask_align_quad_x: true,
    mask_align_use_centroid: true,
    mask_align_flip_x: false,
    cover_offset_x: 0,
    cover_offset_y: 0,
    render_scale: 2,
  },
  {
    id: "simple_flat_example",
    template_path: "mockups/02.png",
    mode: "simple",
    card_geometry: "axis_rect",
    fit: "contain",
    cover_anchor: "center",
    white_threshold: 240,
    mask_expand_px: 2,
    mask_feather_px: 0.8,
    render_scale: 2,
  },
  {
    id: "simple_tilted_example",
    template_path: "mockups/02.png",
    mode: "simple",
    card_geometry: "quad",
    fit: "contain",
    cover_anchor: "center",
    white_threshold: 240,
    mask_expand_px: 2,
    mask_feather_px: 0.8,
    cover_offset_x: 0,
    cover_offset_y: 0,
    render_scale: 2,
  },
];

function normalizeAssetUrls(items) {
  return (items || []).map((item) => ({
    ...item,
    id: item.id || item.name,
    displayName: item.displayName || item.name,
    originalName: item.name,
    url: item.url?.startsWith("http") ? item.url : `${apiBase}${item.url}`,
  }));
}

function fileItemsFromList(fileList) {
  return Array.from(fileList || []).map((file, index) => ({
    id: `${file.name}-${index}-${file.lastModified}`,
    file,
    name: file.name,
    originalName: file.name,
    displayName: file.name,
    url: URL.createObjectURL(file),
  }));
}

function mergeFileItems(existingItems, incomingItems) {
  const seen = new Set(existingItems.map((item) => `${item.name}-${item.file?.size ?? 0}-${item.file?.lastModified ?? 0}`));
  const appended = incomingItems.filter((item) => {
    const key = `${item.name}-${item.file?.size ?? 0}-${item.file?.lastModified ?? 0}`;
    if (seen.has(key)) {
      URL.revokeObjectURL(item.url);
      return false;
    }
    seen.add(key);
    return true;
  });
  return [...existingItems, ...appended];
}

export default function MockupPositionTool() {
  const [mockups, setMockups] = useState([]);
  const [inputs, setInputs] = useState([]);
  const [outputs, setOutputs] = useState([]);
  const [previewSelection, setPreviewSelection] = useState({ group: null, id: null });
  const [activeUseCaseId, setActiveUseCaseId] = useState(USE_CASES[0].id);
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES);
  const [activeTemplateIndex, setActiveTemplateIndex] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);
  const [isTemplateEditingEnabled, setIsTemplateEditingEnabled] = useState(false);
  const [isTemplateSettingsOpen, setIsTemplateSettingsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [activeOutputFolder, setActiveOutputFolder] = useState(null);

  const activeUseCase = useMemo(
    () => USE_CASES.find((useCase) => useCase.id === activeUseCaseId) || USE_CASES[0],
    [activeUseCaseId],
  );

  const filteredTemplateEntries = useMemo(
    () =>
      templates
        .map((template, index) => ({ index, template }))
        .filter(({ template }) => template.mode === activeUseCase.id),
    [templates, activeUseCase.id],
  );

  const activeTemplate = templates[activeTemplateIndex] || null;

  const templatePathOptions = useMemo(() => {
    const fromUploads = mockups
      .map((item) => `mockups/${(item.displayName || item.name || "").trim() || item.name}`)
      .filter(Boolean);
    return Array.from(new Set(fromUploads));
  }, [mockups]);

  const selectedPreview = useMemo(() => {
    if (previewSelection.group === "mockups") return mockups.find((item) => item.id === previewSelection.id) || null;
    if (previewSelection.group === "inputs") return inputs.find((item) => item.id === previewSelection.id) || null;
    if (previewSelection.group === "outputs") return outputs.find((item) => item.id === previewSelection.id) || null;
    return null;
  }, [inputs, mockups, outputs, previewSelection]);

  const outputFolders = useMemo(() => {
    const folderMap = new Map();
    for (const item of outputs) {
      const path = String(item.name || "");
      const parts = path.split("/");
      const folder = parts.length > 1 ? parts[0] : "root";
      const fileName = parts.length > 1 ? parts.slice(1).join("/") : path;
      if (!folderMap.has(folder)) folderMap.set(folder, []);
      folderMap.get(folder).push({ ...item, fileName });
    }
    return Array.from(folderMap.entries())
      .map(([folder, files]) => ({ folder, files }))
      .sort((a, b) => a.folder.localeCompare(b.folder));
  }, [outputs]);

  const resolvedActiveOutputFolder = useMemo(() => {
    if (outputFolders.length === 0) return null;
    if (activeOutputFolder && outputFolders.some((entry) => entry.folder === activeOutputFolder)) {
      return activeOutputFolder;
    }
    return outputFolders[0].folder;
  }, [activeOutputFolder, outputFolders]);

  const activeOutputFiles = useMemo(() => {
    if (!resolvedActiveOutputFolder) return [];
    const found = outputFolders.find((entry) => entry.folder === resolvedActiveOutputFolder);
    return found ? found.files : [];
  }, [resolvedActiveOutputFolder, outputFolders]);

  const setPreviewAndSyncTemplatePath = (group, id) => {
    setPreviewSelection({ group, id });
    if (group !== "mockups") return;

    const selectedMockup = mockups.find((item) => item.id === id);
    if (!selectedMockup) return;

    const nextTemplatePath = `mockups/${getFinalFileName(selectedMockup)}`;
    setTemplates((prev) => {
      const next = [...prev];
      if (!next[activeTemplateIndex]) return prev;
      next[activeTemplateIndex] = {
        ...next[activeTemplateIndex],
        template_path: nextTemplatePath,
      };
      return next;
    });
  };

  const refreshOutputs = async () => {
    const data = await api.getAssets();
    setOutputs(normalizeAssetUrls(data.outputs));
  };

  const refreshTemplates = async () => {
    const data = await api.getTemplates();
    if (!Array.isArray(data.templates)) {
      setTemplates(DEFAULT_TEMPLATES);
      return;
    }

    // Keep right panel stable: always preserve the full known template set.
    const byId = new Map(data.templates.map((template) => [template.id, template]));
    const merged = DEFAULT_TEMPLATES.map((template) => byId.get(template.id) || template);
    setTemplates(merged);
  };

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        await Promise.all([refreshOutputs(), refreshTemplates()]);
      } catch (error) {
        setStatusMessage(error.message || "Failed to load data");
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  const getFinalFileName = (item) => {
    const raw = (item.displayName || "").trim();
    return raw || item.name;
  };

  const appendToList = (setter, prev, fileList) => {
    const incomingItems = fileItemsFromList(fileList);
    const mergedItems = mergeFileItems(prev, incomingItems);
    setter(mergedItems);
    return mergedItems;
  };

  const onMockupsUpload = async (event) => {
    const items = appendToList(setMockups, mockups, event.target.files);
    const hasCurrentPreviewMockup =
      previewSelection.group === "mockups" &&
      items.some((item) => item.id === previewSelection.id);
    const preferredId = hasCurrentPreviewMockup ? previewSelection.id : items[0]?.id;
    if (preferredId) setPreviewAndSyncTemplatePath("mockups", preferredId);
    try {
      await api.uploadTempMockups(items.map(toUploadFile).filter(Boolean));
      setStatusMessage("Mockups synced to backend temp folder.");
    } catch (error) {
      setStatusMessage(error.message || "Failed to sync mockups to backend temp folder.");
    }
    event.target.value = "";
  };

  const onInputsUpload = async (event) => {
    const items = appendToList(setInputs, inputs, event.target.files);
    if (items[0]) setPreviewAndSyncTemplatePath("inputs", items[0].id);
    try {
      await api.uploadTempInputs(items.map(toUploadFile).filter(Boolean));
      setStatusMessage("Input images synced to backend temp folder.");
    } catch (error) {
      setStatusMessage(error.message || "Failed to sync input images to backend temp folder.");
    }
    event.target.value = "";
  };

  const sanitizeRename = (name) => name.replace(/[\\/:*?"<>|]/g, "").trimStart();

  const renameInGroup = (group, id, newName) => {
    const safeName = sanitizeRename(newName);
    const updater = (items) => items.map((item) => (item.id === id ? { ...item, displayName: safeName } : item));
    if (group === "mockups") setMockups(updater);
    if (group === "inputs") setInputs(updater);
    if (group === "outputs") setOutputs(updater);
  };

  const commitRenameInGroup = async (group, id) => {
    if (group === "outputs") return;
    const list = group === "mockups" ? mockups : inputs;
    const item = list.find((entry) => entry.id === id);
    if (!item) return;
    const nextName = sanitizeRename(item.displayName || item.name);
    if (!nextName) return;
    const updater = (items) =>
      items.map((entry) =>
        entry.id === id
          ? { ...entry, name: nextName, displayName: nextName }
          : entry,
      );
    if (group === "mockups") {
      setMockups(updater);
      if (previewSelection.id === id) {
        setTemplates((prev) => {
          const next = [...prev];
          if (!next[activeTemplateIndex]) return prev;
          next[activeTemplateIndex] = {
            ...next[activeTemplateIndex],
            template_path: `mockups/${nextName}`,
          };
          return next;
        });
      }
    } else {
      setInputs(updater);
    }
  };

  const removeFileFromGroup = (group, id) => {
    const removeFrom = (items) => {
      const target = items.find((item) => item.id === id);
      if (target && target.url?.startsWith("blob:")) {
        URL.revokeObjectURL(target.url);
      }
      return items.filter((item) => item.id !== id);
    };
    const execute = async () => {
      try {
        if (group === "mockups") setMockups(removeFrom);
        else if (group === "inputs") setInputs(removeFrom);
        else {
          const target = outputs.find((item) => item.id === id);
          if (!target) return;
          await api.deleteAsset(group, target.originalName || target.name);
          await refreshOutputs();
        }
        if (previewSelection.group === group && previewSelection.id === id) {
          setPreviewSelection({ group: null, id: null });
        }
      } catch (error) {
        setStatusMessage(error.message || "Delete failed");
      }
    };
    execute();
  };

  const clearGroup = (group) => {
    const execute = async () => {
      try {
        if (group === "mockups") {
          mockups.forEach((item) => {
            if (item.url?.startsWith("blob:")) URL.revokeObjectURL(item.url);
          });
          setMockups([]);
        } else if (group === "inputs") {
          inputs.forEach((item) => {
            if (item.url?.startsWith("blob:")) URL.revokeObjectURL(item.url);
          });
          setInputs([]);
        } else {
          await api.clearAssets(group);
          await refreshOutputs();
        }
        if (previewSelection.group === group) {
          setPreviewSelection({ group: null, id: null });
        }
      } catch (error) {
        setStatusMessage(error.message || "Clear failed");
      }
    };
    execute();
  };

  const deleteOutputFile = (filePath) => {
    const execute = async () => {
      try {
        await api.deleteOutputFile(filePath);
        await refreshOutputs();
        if (previewSelection.group === "outputs" && previewSelection.id === filePath) {
          setPreviewSelection({ group: null, id: null });
        }
      } catch (error) {
        setStatusMessage(error.message || "Failed to delete output file.");
      }
    };
    execute();
  };

  const deleteOutputFolder = (folderName) => {
    const execute = async () => {
      try {
        await api.deleteOutputFolder(folderName);
        await refreshOutputs();
        if (resolvedActiveOutputFolder === folderName) {
          setActiveOutputFolder(null);
        }
      } catch (error) {
        setStatusMessage(error.message || "Failed to delete output folder.");
      }
    };
    execute();
  };

  const onUseCaseChange = (useCaseId) => {
    setActiveUseCaseId(useCaseId);
    const firstMatching = templates.findIndex((template) => template.mode === useCaseId);
    if (firstMatching >= 0) {
      setActiveTemplateIndex(firstMatching);
    }
  };

  const parseTemplateFieldValue = (key, value) => {
    const currentValue = activeTemplate?.[key];
    if (typeof currentValue === "number") {
      const parsed = Number(value);
      return Number.isNaN(parsed) ? currentValue : parsed;
    }
    if (typeof currentValue === "boolean") {
      return Boolean(value);
    }
    return value;
  };

  const updateTemplateField = (key, value) => {
    if (!isTemplateEditingEnabled) {
      const confirmed = window.confirm("Do you want to enable editing for template values?");
      if (!confirmed) return;
      setIsTemplateEditingEnabled(true);
    }
    const parsedValue = parseTemplateFieldValue(key, value);
    setTemplates((prev) => {
      const next = [...prev];
      next[activeTemplateIndex] = { ...(next[activeTemplateIndex] || {}), [key]: parsedValue };
      return next;
    });
  };

  const requestOpenTemplateSettings = () => {
    if (isTemplateSettingsOpen) {
      setIsTemplateSettingsOpen(false);
      return;
    }
    const confirmed = window.confirm("Open Template Settings section?");
    if (confirmed) {
      setIsTemplateSettingsOpen(true);
    }
  };

  const getSelectOptionsForField = (key) => {
    if (key === "mode") {
      // Keep template mode aligned with selected use case to avoid mixing.
      return [activeUseCase.id];
    }
    if (key === "template_path") {
      return templatePathOptions.length > 0 ? templatePathOptions : ["No mockups available"];
    }
    return SELECT_FIELD_OPTIONS[key] || null;
  };

  const resetTemplateToDefault = () => {
    if (!activeTemplate) return;
    const defaultTemplate = DEFAULT_TEMPLATES.find((template) => template.id === activeTemplate.id);
    if (!defaultTemplate) return;
    setTemplates((prev) => {
      const next = [...prev];
      next[activeTemplateIndex] = { ...defaultTemplate };
      return next;
    });
  };

  const downloadTemplateConfig = () => {
    const blob = new Blob([JSON.stringify(templates, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "template_config.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const toUploadFile = (item) => {
    if (!item.file) return null;
    const nextName = getFinalFileName(item);
    if (item.file.name === nextName) return item.file;
    return new File([item.file], nextName, {
      type: item.file.type || "application/octet-stream",
      lastModified: item.file.lastModified,
    });
  };

  const handleGenerateMockups = async () => {
    setIsGenerating(true);
    setIsLoading(true);
    try {
      if (!activeTemplate) {
        setStatusMessage("No active template selected.");
        return;
      }

      const templatesForRun = [activeTemplate];
      const mockupFiles = mockups.map(toUploadFile).filter(Boolean);
      const inputFiles = inputs.map(toUploadFile).filter(Boolean);

      console.log("Current template selected for generation:");
      console.log(JSON.stringify(templatesForRun[0], null, 2));

      if (mockupFiles.length > 0) {
        await api.uploadTempMockups(mockupFiles);
      }
      if (inputFiles.length > 0) {
        await api.uploadTempInputs(inputFiles);
      }
      const result = await api.generate(templatesForRun);
      await refreshOutputs();
      setStatusMessage(result.stdout?.trim() || "Generation completed.");
    } catch (error) {
      setStatusMessage(error.message || "Generation failed");
    } finally {
      setIsGenerating(false);
      setIsLoading(false);
    }
  };

  const previewLabel = selectedPreview
    ? `${previewSelection.group?.slice(0, -1) || "image"}: ${getFinalFileName(selectedPreview)}`
    : "No image selected";

  const renderFileGroup = ({ title, items, group, colorClasses, onUpload, hideUpload = false }) => (
    <div className={`space-y-3 rounded-2xl border p-4 shadow-sm ${colorClasses.wrapper}`}>
      <div className="flex items-center justify-between">
        <p className="text-base font-semibold text-slate-800">{title}</p>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-xs font-semibold text-slate-600 shadow-sm">{items.length} items</span>
          {items.length > 0 && (
            <button
              type="button"
              onClick={() => clearGroup(group)}
              className="rounded-lg bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-sm transition hover:bg-slate-100"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {!hideUpload && (
        <label className="block">
          <input type="file" multiple accept="image/*" onChange={onUpload} className="hidden" />
          <span className={`flex w-full cursor-pointer items-center justify-center rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${colorClasses.chooseButton}`}>
            Choose files
          </span>
        </label>
      )}

      <div className={`max-h-72 space-y-2 overflow-auto rounded-xl border bg-white/90 p-2 ${colorClasses.listBorder}`}>
        {items.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-200 px-3 py-5 text-center text-xs text-slate-400">
            No files yet
          </div>
        )}

        {items.map((item) => {
          const isSelected = previewSelection.group === group && previewSelection.id === item.id;
          return (
            <div
              key={item.id}
              role="button"
              tabIndex={0}
              onClick={() => setPreviewAndSyncTemplatePath(group, item.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setPreviewAndSyncTemplatePath(group, item.id);
                }
              }}
              className={`rounded-xl border p-3 transition cursor-pointer ${
                isSelected
                  ? `${colorClasses.activeBorder} ${colorClasses.activeBg} shadow-md ring-1 ring-white`
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 hover:shadow-sm"
              }`}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="truncate text-xs font-semibold text-slate-700">{getFinalFileName(item)}</div>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    removeFileFromGroup(group, item.id);
                  }}
                  className="inline-flex items-center gap-1 rounded border border-red-200 bg-red-50 px-2 py-1 text-[11px] font-semibold text-red-600 hover:bg-red-100"
                  title="Delete image"
                >
                  <FiTrash2 size={12} />
                  Delete
                </button>
              </div>
              <input
                value={item.displayName}
                onClick={(event) => event.stopPropagation()}
                onChange={(event) => renameInGroup(group, item.id, event.target.value)}
                onBlur={() => commitRenameInGroup(group, item.id)}
                className={`w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs ${colorClasses.focus}`}
                placeholder="Rename file"
              />
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderOutputsGroup = () => (
    <div className="space-y-3 rounded-2xl border border-[#7c63b8] bg-gradient-to-br from-[#cbc1e6] to-[#b7a8dc] p-4 shadow-[0_10px_24px_-14px_rgba(54,33,108,0.52)]">
      <div className="flex items-center justify-between">
        <p className="text-base font-semibold text-slate-800">Generated Outputs</p>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-white/70 px-2 py-0.5 text-xs font-semibold text-slate-600 shadow-sm">
            {outputs.length} files
          </span>
          {outputs.length > 0 && (
            <button
              type="button"
              onClick={() => clearGroup("outputs")}
              className="rounded-lg bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-sm transition hover:bg-slate-100"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-2 rounded-xl border border-[#a594d2] bg-white/90 p-2">
        {outputFolders.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-200 px-3 py-5 text-center text-xs text-slate-400">
            No generated folders yet
          </div>
        )}
        {outputFolders.map((entry) => (
          <div
            key={entry.folder}
            className={`w-full rounded-lg border px-3 py-2 transition ${
              entry.folder === resolvedActiveOutputFolder
                ? "border-[#50368c] bg-[#e2dbf4] text-[#3e2a6b]"
                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setActiveOutputFolder(entry.folder)}
                className="min-w-0 flex-1 truncate text-left text-sm font-semibold cursor-pointer"
              >
                {entry.folder}
                <span className="ml-2 text-xs font-medium text-slate-500">({entry.files.length})</span>
              </button>
              <a
                href={api.downloadOutputFolder(entry.folder)}
                className="rounded border border-[#765ab7] bg-[#f0ebff] px-2 py-1 text-[11px] font-semibold text-[#50368c] hover:bg-[#e7ddff]"
              >
                Download
              </a>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  deleteOutputFolder(entry.folder);
                }}
                className="inline-flex items-center justify-center rounded border border-red-200 bg-red-50 p-1.5 text-red-600 hover:bg-red-100"
                title="Delete folder"
              >
                <FiTrash2 size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {resolvedActiveOutputFolder && (
        <div className="space-y-2 rounded-xl border border-[#a594d2] bg-white/90 p-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Folder: {resolvedActiveOutputFolder}
          </div>
          <div className="max-h-56 space-y-2 overflow-auto">
            {activeOutputFiles.map((item) => {
              const isSelected = previewSelection.group === "outputs" && previewSelection.id === item.id;
              return (
                <div
                  key={item.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setPreviewAndSyncTemplatePath("outputs", item.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setPreviewAndSyncTemplatePath("outputs", item.id);
                    }
                  }}
                  className={`rounded-lg border p-2 transition cursor-pointer ${
                    isSelected
                      ? "border-[#50368c] bg-[#e2dbf4] shadow-md ring-1 ring-white"
                      : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 hover:shadow-sm"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate text-xs font-semibold text-slate-700">{item.fileName}</div>
                    <a
                      href={api.downloadOutputFile(item.name)}
                      download={item.fileName}
                      onClick={(event) => event.stopPropagation()}
                      className="rounded border border-[#765ab7] bg-[#f0ebff] px-2 py-1 text-[11px] font-semibold text-[#50368c] hover:bg-[#e7ddff]"
                    >
                      Download
                    </a>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        deleteOutputFile(item.name);
                      }}
                      className="inline-flex items-center justify-center rounded border border-red-200 bg-red-50 p-1.5 text-red-600 hover:bg-red-100"
                      title="Delete file"
                    >
                      <FiTrash2 size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Mock Generator Studio</h1>
            <p className="text-sm text-slate-500">
              Backend-driven workflow: manage files, templates, and config for script-based generation.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {isLoading && (
              <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
                Syncing...
              </span>
            )}
            <a
              href={api.downloadOutputs()}
              className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
            >
              Download Outputs
            </a>
            <button
              type="button"
              onClick={handleGenerateMockups}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
            >
              {isGenerating ? "Preparing..." : "Generate Mockups"}
            </button>
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">Backend Aligned UI</span>
          </div>
        </div>
      </header>
      {statusMessage && (
        <div className="mx-auto mt-3 max-w-[1600px] rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm">
          {statusMessage}
        </div>
      )}

      <main className={`mx-auto grid max-w-[1600px] grid-cols-1 gap-4 p-4 xl:items-start ${isRightPanelOpen ? "xl:grid-cols-[360px_1fr_420px]" : "xl:grid-cols-[360px_1fr]"}`}>
        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm xl:sticky xl:top-4 xl:h-[calc(100vh-2rem)] xl:overflow-y-auto">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-800">Assets</h2>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
              {mockups.length + inputs.length + outputs.length} files
            </span>
          </div>

          {renderFileGroup({
            title: "Mockups Folder",
            items: mockups,
            group: "mockups",
            onUpload: onMockupsUpload,
            colorClasses: {
              wrapper: "border-[#4f7f81] bg-gradient-to-br from-[#b7d0d1] to-[#a2c4c5] shadow-[0_10px_24px_-14px_rgba(32,67,69,0.55)]",
              chooseButton: "border-[#3f6d6f] bg-[#2f6163] text-white shadow-md hover:bg-[#275355] hover:border-[#365f61]",
              listBorder: "border-[#7ea9ab]",
              activeBorder: "border-[#2f6163]",
              activeBg: "bg-[#d5e7e8]",
              focus: "focus:border-[#2f6163] focus:outline-none focus:ring-1 focus:ring-[#2f6163]",
            },
          })}

          {renderFileGroup({
            title: "Input Images Folder",
            items: inputs,
            group: "inputs",
            onUpload: onInputsUpload,
            colorClasses: {
              wrapper: "border-[#4b9a7f] bg-gradient-to-br from-[#b7decf] to-[#9dd0bc] shadow-[0_10px_24px_-14px_rgba(18,75,57,0.5)]",
              chooseButton: "border-[#2f7f62] bg-[#1f6f53] text-white shadow-md hover:bg-[#195d46] hover:border-[#286a53]",
              listBorder: "border-[#7ebca7]",
              activeBorder: "border-[#1f6f53]",
              activeBg: "bg-[#d4ece3]",
              focus: "focus:border-[#1f6f53] focus:outline-none focus:ring-1 focus:ring-[#1f6f53]",
            },
          })}

          {renderOutputsGroup()}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2">
            <h2 className="text-base font-semibold">Image Preview</h2>
            <span className="text-slate-300">-</span>
            <p className="truncate text-sm text-slate-600">{previewLabel}</p>
          </div>

          <div className="relative flex h-[680px] items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
            {selectedPreview ? (
              <img
                key={`${previewSelection.group}-${previewSelection.id}`}
                src={selectedPreview.url}
                alt={getFinalFileName(selectedPreview)}
                className="h-full w-full object-contain p-2"
              />
            ) : (
              <p className="text-sm text-slate-500">Upload files and select any filename from mockups, inputs, or outputs.</p>
            )}
          </div>
        </section>

        {isRightPanelOpen && (
        <section className="space-y-4 self-start rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Use Cases & Template Config</h2>
            <button
              type="button"
              onClick={() => setIsRightPanelOpen(false)}
                className="rounded-md border border-indigo-300 bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-700 shadow-[0_3px_0_0_rgba(99,102,241,0.35)] transition hover:bg-indigo-200 active:translate-y-[1px] active:shadow-[0_1px_0_0_rgba(99,102,241,0.35)]"
            >
              Hide
            </button>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="useCaseSelect">Apply use case to selected template</label>
            <select
              id="useCaseSelect"
              value={activeUseCaseId}
              onChange={(event) => onUseCaseChange(event.target.value)}
              className="w-full rounded-lg border border-slate-300 p-2 text-sm"
            >
              {USE_CASES.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium" htmlFor="templateIndex">Template entries</label>
              <button
                type="button"
                onClick={resetTemplateToDefault}
                className="rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700 shadow-[0_3px_0_0_rgba(217,119,6,0.35)] transition hover:bg-amber-200 active:translate-y-[1px] active:shadow-[0_1px_0_0_rgba(217,119,6,0.35)]"
              >
                Reset Default
              </button>
            </div>
            <select
              id="templateIndex"
              value={activeTemplateIndex}
              onChange={(event) => setActiveTemplateIndex(Number(event.target.value))}
              className="w-full rounded-lg border border-slate-300 p-2 text-sm"
            >
              {filteredTemplateEntries.map(({ template, index }) => (
                <option key={`${template.id}-${index}`} value={index}>
                  {template.id}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50 to-sky-50 p-3 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Template Settings (backend keys)</h3>
              <button
                type="button"
                onClick={requestOpenTemplateSettings}
                className="rounded-md bg-sky-100 px-2 py-1 text-[11px] font-semibold text-sky-700 shadow-[0_3px_0_0_rgba(14,165,233,0.35)] transition hover:bg-sky-200 active:translate-y-[1px] active:shadow-[0_1px_0_0_rgba(14,165,233,0.35)]"
              >
                {isTemplateSettingsOpen ? "Close" : "Open"}
              </button>
            </div>

            {isTemplateSettingsOpen && activeTemplate && (
              <div className="mt-3 space-y-3">
                <div className="flex items-center justify-end">
                  <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${isTemplateEditingEnabled ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
                    {isTemplateEditingEnabled ? "Edit enabled" : "Read only"}
                  </span>
                </div>
                {BACKEND_TEMPLATE_KEYS.map((key) => (
                  <div key={key} className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">{key}</label>
                    {getSelectOptionsForField(key) ? (
                      <select
                        value={
                          key === "template_path" && templatePathOptions.length === 0
                            ? "No mockups available"
                            : String(activeTemplate[key] ?? "")
                        }
                        onChange={(event) => updateTemplateField(key, event.target.value)}
                        className="w-full rounded-lg border border-slate-300 bg-white p-2 text-sm"
                        disabled={key === "template_path" && templatePathOptions.length === 0}
                      >
                        {getSelectOptionsForField(key).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : typeof activeTemplate[key] === "boolean" ? (
                      <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                        <input
                          type="checkbox"
                          checked={Boolean(activeTemplate[key])}
                          onChange={(event) => updateTemplateField(key, event.target.checked)}
                        />
                        <span>{String(activeTemplate[key])}</span>
                      </label>
                    ) : (
                      <input
                        type={typeof activeTemplate[key] === "number" ? "number" : "text"}
                        value={String(activeTemplate[key] ?? "")}
                        onChange={(event) => updateTemplateField(key, event.target.value)}
                        className="w-full rounded-lg border border-slate-300 bg-white p-2 text-sm"
                      />
                    )}
                  </div>
                ))}

                <div className="space-y-1 rounded-lg border border-indigo-200 bg-white p-3 text-xs text-slate-600">
                  <p className="font-semibold text-slate-700">How to run backend</p>
                  <p>1) Put mockups in `backend/mockups`, inputs in `backend/input_images`.</p>
                  <p>2) Save downloaded config as `backend/template_config.json`.</p>
                  <p>3) Run `python script.py` inside `backend`.</p>
                </div>

                <button
                  type="button"
                  onClick={downloadTemplateConfig}
                  className="w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                >
                  Download template_config.json
                </button>

                <pre className="max-h-44 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                  {JSON.stringify(
                    {
                      selected: previewSelection,
                      selected_name: selectedPreview ? getFinalFileName(selectedPreview) : null,
                      template_config_preview: templates,
                    },
                    null,
                    2,
                  )}
                </pre>
              </div>
            )}
          </div>
        </section>
        )}

        {!isRightPanelOpen && (
          <button
            type="button"
            onClick={() => setIsRightPanelOpen(true)}
            className="fixed bottom-6 right-6 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-lg hover:bg-slate-800"
          >
            Open Template Panel
          </button>
        )}
      </main>
    </div>
  );
}