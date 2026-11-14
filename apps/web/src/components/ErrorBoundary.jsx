import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <div role="alert" className="rounded border border-grid bg-panel p-4 text-sm text-slate-200"><p>This view could not be displayed.</p><button className="mt-2 rounded border border-cyan px-3 py-1" onClick={() => this.setState({ failed: false })}>Try again</button></div>;
    return this.props.children;
  }
}
