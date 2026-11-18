export function renderHighlightedText(text, highlight) {
  if (!highlight) return [{ text, highlight: false }];
  const index = text.toLowerCase().indexOf(highlight.toLowerCase());
  if (index === -1) return [{ text, highlight: false }];

  const before = text.slice(0, index);
  const hit = text.slice(index, index + highlight.length);
  const after = text.slice(index + highlight.length);

  return [
    { text: before, highlight: false },
    { text: hit, highlight: true },
    { text: after, highlight: false },
  ].filter((p) => p.text.length > 0);
}
