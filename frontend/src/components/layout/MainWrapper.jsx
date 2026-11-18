import { cloneElement, useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { useLocation } from "react-router-dom";
import { SidePanel } from "../ui/SidePanel";

export function MainWrapper({ sidebar, children }) {
  const [wide, setWide] = useState(() => window.innerWidth >= 1024);
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => {
    const resize = () => setWide(window.innerWidth >= 1024);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  useEffect(() => { setOpen(false); }, [location.pathname]);
  return <div className="flex h-full min-w-0 bg-bg">
    {wide ? <div className="h-full w-[260px] shrink-0">{sidebar}</div> : <>
      <button type="button" className="response-icon fixed left-2 top-2.5 z-20 bg-bg" aria-label="Open navigation" title="Open navigation"
        onClick={() => setOpen(true)}><Menu size={20} /></button>
      {open && <SidePanel title="Navigation" onClose={() => setOpen(false)}>
        <div className="-m-5 h-[calc(100%+40px)]">{cloneElement(sidebar, { onNavigate: () => setOpen(false) })}</div>
      </SidePanel>}
    </>}
    <main className="min-w-0 flex-1"><div className="h-full overflow-hidden">{children}</div></main>
  </div>;
}
