export function Card({ className = "", children }) {
  return (
    <div className={`rounded-lg border border-border bg-surface ${className}`}>{children}</div>
  );
}

export function CardHeader({ className = "", children }) {
  return <div className={`px-4 pt-4 ${className}`}>{children}</div>;
}

export function CardTitle({ className = "", children }) {
  return <div className={`text-sm font-semibold text-text ${className}`}>{children}</div>;
}

export function CardDescription({ className = "", children }) {
  return <div className={`text-sm text-muted ${className}`}>{children}</div>;
}

export function CardContent({ className = "", children }) {
  return <div className={`px-4 pb-4 ${className}`}>{children}</div>;
}
