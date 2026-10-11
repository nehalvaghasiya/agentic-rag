export function MainWrapper({ sidebar, children }) {
  return (
    <div className="flex h-full bg-bg">
      {sidebar}
      <main className="min-w-0 flex-1">
        <div className="h-full overflow-hidden">{children}</div>
      </main>
    </div>
  );
}
