export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  disabled = false,
  type = "button",
  onClick,
  children,
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-md border text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:opacity-50 disabled:cursor-not-allowed";

  const variants = {
    primary: "bg-accent text-white border-accent hover:bg-accent/90",
    secondary: "bg-surface text-text border-border hover:bg-border/40",
    ghost: "bg-transparent text-text border-transparent hover:bg-border/30",
  };

  const sizes = {
    sm: "h-8 px-3",
    md: "h-9 px-4",
    lg: "h-10 px-5",
  };

  return (
    <button
      type={type}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
