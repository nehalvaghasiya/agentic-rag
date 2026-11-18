import { Component } from "react";

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full items-center justify-center bg-bg px-6">
          <div className="w-full max-w-xl rounded-lg border border-border bg-surface p-6">
            <div className="text-sm font-semibold text-text">App error</div>
            <div className="mt-2 text-xs text-muted">
              The UI crashed while rendering. Open DevTools Console for details.
            </div>
            <pre className="mt-4 max-h-60 overflow-auto rounded-md border border-border bg-bg p-3 text-[11px] text-text">
              {String(this.state.error?.stack || this.state.error)}
            </pre>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
