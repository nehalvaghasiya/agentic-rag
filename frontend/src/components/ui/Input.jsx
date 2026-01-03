export function Input({
  value,
  onChange,
  placeholder,
  className = "",
  type = "text",
  ...rest
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className={`h-10 w-full rounded-md border border-border bg-bg px-3 text-sm text-text placeholder:text-muted/70 focus:outline-none focus:ring-2 focus:ring-accent/40 ${className}`}
      {...rest}
    />
  );
}
