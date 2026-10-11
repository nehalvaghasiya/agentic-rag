export function ProgressBar({ value }) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-border/50">
      <div
        className="h-full bg-accent transition-[width] duration-150"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
