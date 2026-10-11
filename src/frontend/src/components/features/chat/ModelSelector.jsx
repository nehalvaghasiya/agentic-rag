import { useState, useRef, useEffect } from "react";
import { ChevronDown, Settings, Check, Plus, Cpu } from "lucide-react";
import { ModelConfigModal } from "./ModelConfigModal";

export function ModelSelector({ 
  models, 
  selectedModelId, 
  onSelectModel, 
  onAddModel,
  onUpdateModel,
  onDeleteModel 
}) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [editingModel, setEditingModel] = useState(null);
  const dropdownRef = useRef(null);

  const selectedModel = models.find((m) => m.id === selectedModelId) || models[0];

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleOpenSettings = (e, model = null) => {
    e.stopPropagation();
    setEditingModel(model);
    setShowConfigModal(true);
    setShowDropdown(false);
  };

  const handleSaveModel = (modelData) => {
    if (editingModel) {
      onUpdateModel(editingModel.id, modelData);
    } else {
      onAddModel(modelData);
    }
    setShowConfigModal(false);
    setEditingModel(null);
  };

  const handleDeleteModel = (modelId) => {
    onDeleteModel(modelId);
    setShowConfigModal(false);
    setEditingModel(null);
  };

  return (
    <>
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setShowDropdown(!showDropdown)}
          className="flex h-11 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-text transition-colors hover:bg-border/30"
          title="Select model"
        >
          <Cpu size={16} className="text-muted" />
          <span className="max-w-[120px] truncate">{selectedModel?.name || "Select model"}</span>
          <ChevronDown size={14} className="text-muted" />
        </button>

        {showDropdown && (
          <div className="absolute bottom-full left-0 mb-2 w-72 rounded-md border border-border bg-surface shadow-lg z-50">
            <div className="p-2">
              <div className="px-2 py-1.5 text-xs font-medium text-muted">
                Model Configuration
              </div>
              
              {models.map((model) => (
                <div
                  key={model.id}
                  className={`mt-1 flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors hover:bg-border/30 ${
                    selectedModelId === model.id ? "bg-accent/10" : ""
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => {
                      onSelectModel(model.id);
                      setShowDropdown(false);
                    }}
                    className="flex flex-1 items-center gap-2 text-left"
                  >
                    {selectedModelId === model.id ? (
                      <Check size={14} className="text-accent" />
                    ) : (
                      <div className="w-[14px]" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className={`truncate ${selectedModelId === model.id ? "text-accent" : "text-text"}`}>
                        {model.name}
                      </div>
                      <div className="truncate text-xs text-muted">
                        {model.model || "Default model"}
                      </div>
                    </div>
                  </button>
                  
                  {!model.isDefault && (
                    <button
                      type="button"
                      onClick={(e) => handleOpenSettings(e, model)}
                      className="p-1 rounded hover:bg-border/50 text-muted hover:text-text"
                      title="Edit configuration"
                    >
                      <Settings size={14} />
                    </button>
                  )}
                </div>
              ))}

              <div className="mt-2 border-t border-border pt-2">
                <button
                  type="button"
                  onClick={(e) => handleOpenSettings(e, null)}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm text-accent transition-colors hover:bg-accent/10"
                >
                  <Plus size={14} />
                  <span>Add new model</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {showConfigModal && (
        <ModelConfigModal
          model={editingModel}
          onSave={handleSaveModel}
          onDelete={editingModel && !editingModel.isDefault ? () => handleDeleteModel(editingModel.id) : null}
          onClose={() => {
            setShowConfigModal(false);
            setEditingModel(null);
          }}
        />
      )}
    </>
  );
}
