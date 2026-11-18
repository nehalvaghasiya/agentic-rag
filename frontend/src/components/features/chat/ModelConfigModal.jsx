import { useState, useEffect } from "react";
import { X, Eye, EyeOff, Trash2, AlertCircle } from "lucide-react";
import { Button } from "../../ui/Button";
import { Input } from "../../ui/Input";

export function ModelConfigModal({ model, onSave, onDelete, onClose }) {
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [errors, setErrors] = useState({});

  const isEditing = model !== null;

  useEffect(() => {
    if (model) {
      setName(model.name || "");
      setApiKey(model.apiKey || "");
      setModelName(model.model || "");
      setBaseUrl(model.baseUrl || "");
    }
  }, [model]);

  const validate = () => {
    const newErrors = {};
    
    if (!name.trim()) {
      newErrors.name = "Display name is required";
    }
    
    if (!apiKey.trim() && !model?.hasApiKey) {
      newErrors.apiKey = "API key is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!validate()) return;

    onSave({
      name: name.trim(),
      apiKey: apiKey.trim() || undefined,
      model: modelName.trim() || undefined,
      baseUrl: baseUrl.trim() || undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border border-border bg-bg shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold text-text">
            {isEditing ? "Edit Model Configuration" : "Add New Model"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted hover:bg-border/30 hover:text-text"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Display Name */}
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">
              Display Name *
            </label>
            <Input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., GPT-4 Turbo, Claude 3, Groq Llama"
              className={errors.name ? "border-red-500" : ""}
            />
            {errors.name && (
              <p className="mt-1 text-xs text-red-400 flex items-center gap-1">
                <AlertCircle size={12} />
                {errors.name}
              </p>
            )}
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">
              API Key *
            </label>
            <div className="relative">
              <Input
                type={showApiKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={isEditing && model?.hasApiKey ? "••••••••••••••••" : "sk-..."}
                className={`pr-10 ${errors.apiKey ? "border-red-500" : ""}`}
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted hover:text-text"
              >
                {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors.apiKey && (
              <p className="mt-1 text-xs text-red-400 flex items-center gap-1">
                <AlertCircle size={12} />
                {errors.apiKey}
              </p>
            )}
            {isEditing && model?.hasApiKey && !apiKey && (
              <p className="mt-1 text-xs text-muted">
                Leave blank to keep existing key
              </p>
            )}
          </div>

          {/* Model Name */}
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">
              Model Name
              <span className="text-muted font-normal ml-1">(optional)</span>
            </label>
            <Input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g., gpt-4o-mini, claude-3-opus, llama-3.3-70b"
            />
            <p className="mt-1 text-xs text-muted">
              Override the default model. Leave blank to use provider default.
            </p>
          </div>

          {/* Base URL */}
          <div>
            <label className="block text-sm font-medium text-text mb-1.5">
              API Base URL
              <span className="text-muted font-normal ml-1">(optional)</span>
            </label>
            <Input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="e.g., https://api.groq.com/openai/v1"
            />
            <p className="mt-1 text-xs text-muted">
              For OpenAI-compatible APIs (Groq, Together, OpenRouter, etc.)
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between pt-4 border-t border-border">
            {onDelete ? (
              <button
                type="button"
                onClick={onDelete}
                className="flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300"
              >
                <Trash2 size={14} />
                Delete
              </button>
            ) : (
              <div />
            )}
            
            <div className="flex items-center gap-2">
              <Button type="button" variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="primary">
                {isEditing ? "Save Changes" : "Add Model"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
