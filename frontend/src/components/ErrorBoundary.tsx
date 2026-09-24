/**
 * Catches a render error in a page and shows a recoverable state instead of
 * an empty screen.
 *
 * Two deliberate choices:
 *
 * It does NOT swallow the error. The original is re-thrown to the console
 * with its component stack, because hiding the cause turns one visible bug
 * into an invisible one.
 *
 * It resets when the route changes (`resetKey`). Without that, one page
 * crashing would leave the error state pinned across every subsequent
 * navigation, which looks exactly like the blank-page bug it exists to
 * prevent.
 */
import { Component, ErrorInfo, ReactNode } from 'react'
import { RefreshCw, TriangleAlert } from 'lucide-react'

interface Props { children: ReactNode; resetKey?: string }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidUpdate(prev: Props) {
    // New route, clear slate.
    if (this.state.error && prev.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface it fully — this is how the real cause gets found.
    console.error('[SmartLab] a page failed to render:', error,
                  info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="surface-pad max-w-lg mx-auto mt-10 text-center">
        <div className="inline-flex items-center justify-center w-11 h-11
                        rounded-xl bg-bad/10 border border-bad/30 text-bad mb-4">
          <TriangleAlert size={18} />
        </div>
        <h2 className="text-base font-semibold text-slate-100">
          This section could not be displayed
        </h2>
        <p className="mt-2 text-sm text-slate-500 leading-relaxed">
          Something went wrong while rendering this page. The rest of the
          portal is unaffected — you can move to another section or try again.
        </p>

        <pre className="mt-4 text-left text-[11px] text-bad/80 bg-ink-900/70
                        border border-ink-600 rounded-lg p-3 overflow-x-auto
                        whitespace-pre-wrap">
          {error.message}
        </pre>

        <button onClick={() => this.setState({ error: null })}
                className="btn-ghost mt-5">
          <RefreshCw size={14} /> Try again
        </button>
      </div>
    )
  }
}
