import { useRef } from "react";
import { FileList } from "./FileList";
import { UploadZone } from "./UploadZone";
import { uploadAccept, validateFiles } from "./uploadRules";

export function DocumentPicker({ files, onChange, onError, disabled = false, label = "Select documents" }) {
  const input = useRef(null);
  function select(selected) {
    const next = [...files, ...selected];
    const error = validateFiles(next);
    onError(error);
    if (!error) onChange(next);
  }
  return <div>
    <input ref={input} aria-label={label} type="file" multiple accept={uploadAccept} disabled={disabled} className="sr-only"
      onChange={event => { select(Array.from(event.target.files || [])); event.target.value = ""; }} />
    <UploadZone onBrowse={() => input.current?.click()} onFiles={select} disabled={disabled} />
    <FileList files={files} disabled={disabled} onRemove={index => { onChange(files.filter((_, i) => i !== index)); onError(""); }} />
  </div>;
}
