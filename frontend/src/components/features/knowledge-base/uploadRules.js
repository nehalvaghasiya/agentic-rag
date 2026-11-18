export const uploadAccept = ".pdf,.docx,.txt,.md,.csv,.json,.html,.htm";
export const supportedTypes = "PDF, DOCX, TXT, Markdown, CSV, JSON, HTML";
export function validateFiles(files) {
  if (files.length > 10) return "Select at most 10 files per upload.";
  for (const file of files) {
    if (!uploadAccept.split(",").includes(`.${file.name.split(".").at(-1).toLowerCase()}`)) return `${file.name}: unsupported file type.`;
    if (!file.size || file.size > 8 * 1024 * 1024) return `${file.name}: files must be non-empty and no larger than 8 MiB.`;
    if (file.name.length > 200 || /\.\.|[/\\]|^\./.test(file.name)) return `${file.name}: choose a safe filename of at most 200 characters.`;
  }
  return "";
}
