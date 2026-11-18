/** Thin v2 client: sends no provider secrets; supports agent SSE replay. */
const URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001';

export async function request(path, init = {}) {
  const response = await fetch(`${URL}/api/v2${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

export function json(method, body) {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

export async function uploadDocuments(kbId, files) {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  return request(`/kb/${encodeURIComponent(kbId)}/documents`, { method: 'POST', body: form });
}

/** The backend returns actual agent/tool events, not hallucinated reasoning text. */
export async function readEvents(runId, onEvent, signal, lastId = 0) {
  const response = await fetch(`${URL}/api/v2/runs/${encodeURIComponent(runId)}/events`, {
    signal, headers: lastId ? { 'Last-Event-ID': String(lastId) } : {},
  });
  if (!response.ok || !response.body) throw new Error('Unable to stream this run');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let cursor = lastId;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, '\n');
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        if (!block.trim() || block.startsWith(':')) continue;
        const lines = block.split('\n');
        const type = lines.find((line) => line.startsWith('event:'))?.slice(6).trim();
        const raw = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n');
        if (!type || !raw) continue;
        const id = Number(lines.find((line) => line.startsWith('id:'))?.slice(3).trim() || cursor);
        if (id <= cursor) continue;
        cursor = id;
        onEvent({ id, type, data: JSON.parse(raw) });
        if (['complete', 'error', 'cancelled'].includes(type)) return cursor;
      }
      if (done) return cursor;
    }
  } finally {
    reader.releaseLock();
  }
}
