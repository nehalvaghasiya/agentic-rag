import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import App from "../App";
import { ErrorBoundary } from "../components/ui/ErrorBoundary";
import { AppStateProvider } from "../state/AppStateContext";

export function renderWithAppProviders(
  ui,
  { route = "/", path = "*" } = {}
) {
  const user = userEvent.setup();
  const result = render(
    <AppStateProvider>
      <MemoryRouter initialEntries={[route]}>
        <ErrorBoundary>
          <Routes>
            <Route path={path} element={ui} />
          </Routes>
        </ErrorBoundary>
      </MemoryRouter>
    </AppStateProvider>
  );

  return { user, ...result };
}

export function renderApp({ route = "/" } = {}) {
  window.history.pushState(null, "", route);
  const user = userEvent.setup();
  const result = render(<App />);

  return { user, ...result };
}
