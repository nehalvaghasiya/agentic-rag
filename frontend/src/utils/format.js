export function formatBytes(bytes) {
  if (bytes < 1000) return `${bytes}B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1000;
  let unitIndex = 0;
  while (value >= 1000 && unitIndex < units.length - 1) {
    value /= 1000;
    unitIndex += 1;
  }
  return `${value.toFixed(2)}${units[unitIndex]}`;
}

export function formatIsoDate(iso) {
  if (!iso || Number.isNaN(new Date(iso).getTime())) return "Unknown";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
