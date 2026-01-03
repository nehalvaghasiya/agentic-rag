import { AnimatePresence, motion } from "framer-motion";

export function Modal({ open, title, onClose, children, footer }) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          aria-modal="true"
          role="dialog"
        >
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
            aria-label="Close modal"
            onClick={onClose}
          />

          <motion.div
            className="relative mx-4 w-full max-w-2xl overflow-hidden rounded-xl border border-border bg-surface"
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.18 }}
          >
            <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
              <div className="text-sm font-semibold text-text">{title}</div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-muted hover:bg-border/30"
              >
                Esc
              </button>
            </div>

            <div className="max-h-[70vh] overflow-auto px-5 py-4">{children}</div>

            {footer ? (
              <div className="border-t border-border px-5 py-4">{footer}</div>
            ) : null}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
