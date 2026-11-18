import {
  File,
  FileCode2,
  FileSpreadsheet,
  FileText,
  FileType2,
} from "lucide-react";

export function getFileIcon(type) {
  const t = (type ?? "").toLowerCase();
  if (t === "pdf") return FileType2;
  if (t === "doc" || t === "docx") return FileText;
  if (t === "txt" || t === "md") return FileCode2;
  if (t === "csv") return FileSpreadsheet;
  return File;
}
