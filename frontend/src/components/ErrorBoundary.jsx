import React from 'react';

export class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        if (import.meta.env.DEV) {
            console.error('ErrorBoundary Caught:', error, errorInfo);
        } else {
            console.error('A page rendering error was caught.');
        }
        this.setState({ errorInfo });
    }

    render() {
        if (this.state.hasError) {
            const isDevelopment = import.meta.env.DEV;
            return (
                <main id="error-dump" role="alert" className="min-h-screen bg-slate-50 px-5 py-12 text-slate-900">
                    <section className="mx-auto max-w-3xl rounded-2xl border border-rose-200 bg-white p-6 shadow-sm sm:p-8">
                        <h1 className="text-xl font-bold">{isDevelopment ? 'This page could not be rendered' : 'Something went wrong'}</h1>
                        <p className="mt-2 text-sm text-slate-600">The error is recorded in the browser console. Reload the page to retry.</p>
                        {isDevelopment && <>
                            <pre className="mt-4 overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-rose-50 p-4 text-sm text-rose-900">{this.state.error && this.state.error.toString()}</pre>
                            <details className="mt-4">
                                <summary className="cursor-pointer text-sm font-semibold text-slate-700">Technical details</summary>
                                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-4 text-xs text-slate-700">{this.state.errorInfo && this.state.errorInfo.componentStack}</pre>
                            </details>
                        </>}
                        <button type="button" onClick={() => window.location.reload()} className="mt-5 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2">Reload page</button>
                    </section>
                </main>
            );
        }
        return this.props.children;
    }
}
