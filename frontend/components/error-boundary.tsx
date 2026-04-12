"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  /** Shown in the fallback UI when an error is caught. */
  label?: string;
}

interface State {
  error: Error | null;
}

/**
 * Class-based error boundary for wrapping individual UI sections.
 *
 * Unlike the Next.js `error.tsx` page-level boundary, this can be placed
 * around any subtree (dashboard charts, map panel, etc.) so that a crash
 * in one section doesn't take down the entire page.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ErrorBoundary${this.props.label ? `: ${this.props.label}` : ""}]`, error, info.componentStack);
  }

  private handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-6 text-center">
          <p className="text-sm font-medium text-destructive">
            {this.props.label
              ? `Failed to load: ${this.props.label}`
              : "Something went wrong in this section"}
          </p>
          <p className="text-xs text-muted-foreground max-w-xs">
            {this.state.error.message}
          </p>
          <Button onClick={this.handleReset} variant="outline" size="sm">
            Try again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
