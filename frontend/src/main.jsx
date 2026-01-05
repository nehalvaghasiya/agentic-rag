import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";

const THEME_STORAGE_KEY = "theme";
try {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
  const shouldUseDark = storedTheme ? storedTheme === "dark" : Boolean(prefersDark);
  document.documentElement.classList.toggle("dark", shouldUseDark);
} catch {
  // Ignore theme init failures (e.g., privacy mode/localStorage blocked).
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

