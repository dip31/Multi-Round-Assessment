import { useState, useRef, useEffect, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Play, Send, Save, Code, Terminal, Bug, Zap } from 'lucide-react';

const LANGUAGE_CONFIG = {
  python: { monaco: 'python', label: 'Python 3', defaultExtension: '.py' },
  javascript: { monaco: 'javascript', label: 'JavaScript (Node.js)', defaultExtension: '.js' },
  java: { monaco: 'java', label: 'Java', defaultExtension: '.java' },
  cpp: { monaco: 'cpp', label: 'C++', defaultExtension: '.cpp' },
};

export default function EditorPanel({
  language,
  onLanguageChange,
  code,
  onCodeChange,
  onRun,
  onSubmit,
  onSave,
  isRunning,
  isSubmitting,
  saveStatus,
  result,
  activeResultTab,
  onResultTabChange,
}) {
  const editorRef = useRef(null);
  const didMountRef = useRef(false);
  const [editorLoaded, setEditorLoaded] = useState(false);
  const [formatOnSave] = useState(true);

  const currentLanguage = LANGUAGE_CONFIG[language] || LANGUAGE_CONFIG.python;

  const handleEditorMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    setEditorLoaded(true);
    didMountRef.current = true;
    
    editor.updateOptions({
      tabSize: language === 'python' ? 4 : 2,
      insertSpaces: true,
      formatOnPaste: true,
      formatOnType: true,
    });

    if (formatOnSave) {
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        onSave?.();
      });
    }
  }, [language, formatOnSave, onSave]);

  // Keep the editor in sync with the parent code state (e.g. starter code
  // loads after mount). Monaco's `value` prop is the source of truth; this
  // only patches position issues after an external value change.
  useEffect(() => {
    if (!didMountRef.current) return;
    if (editorRef.current && code !== editorRef.current.getValue()) {
      editorRef.current.setValue(code);
    }
  }, [code]);

  const getResultStatus = () => {
    if (!result?.raw) return null;
    const status = result.raw.status;
    if (status === 'accepted') return { type: 'success', icon: '✓', label: 'Accepted' };
    if (status === 'wrong_answer') return { type: 'error', icon: '✕', label: 'Wrong Answer' };
    if (status === 'compilation_error') return { type: 'error', icon: '⚠', label: 'Compilation Error' };
    if (status === 'runtime_error') return { type: 'error', icon: '⚠', label: 'Runtime Error' };
    if (status === 'time_limit_exceeded') return { type: 'error', icon: '⏱', label: 'Time Limit Exceeded' };
    if (status === 'memory_limit_exceeded') return { type: 'error', icon: '⚠', label: 'Memory Limit Exceeded' };
    return { type: 'default', icon: '?', label: status || 'Unknown' };
  };

  const statusInfo = getResultStatus();

  return (
    <main className="flex flex-col h-full bg-slate-950">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 bg-slate-950/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400 hidden sm:block">Language</label>
          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/20 appearance-none cursor-pointer"
            aria-label="Programming language"
          >
            {Object.entries(LANGUAGE_CONFIG).map(([key, config]) => (
              <option key={key} value={key} className="bg-slate-900">
                {config.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onSave}
            disabled={saveStatus === 'saving'}
            className="p-2 rounded-xl border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:border-white/20 transition disabled:opacity-50"
            title="Save (Ctrl+S)"
            aria-label="Save code"
          >
            <Save className="w-4 h-4" />
            <span className="hidden sm:inline ml-1 text-xs font-medium">
              {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : 'Save'}
            </span>
          </button>

          <button
            onClick={onRun}
            disabled={isRunning || isSubmitting}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-cyan-400/30 bg-cyan-400/10 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Run visible tests"
          >
            <Play className="w-4 h-4" />
            <span>{isRunning ? 'Running...' : 'Run'}</span>
          </button>

          <button
            onClick={onSubmit}
            disabled={isRunning || isSubmitting}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-400 to-cyan-400 text-sm font-semibold text-slate-950 transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Submit solution"
          >
            <Send className="w-4 h-4" />
            <span>{isSubmitting ? 'Submitting...' : 'Submit'}</span>
          </button>
        </div>
      </div>

      <div className="flex-1 relative min-h-0">
        <Editor
          height="100%"
          language={currentLanguage.monaco}
          theme="vs-dark"
          value={code}
          onChange={onCodeChange}
          onMount={handleEditorMount}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on',
            bracketPairColorization: { enabled: true },
            guides: { bracketPairs: true },
            renderLineHighlight: 'all',
            folding: true,
            matchBrackets: 'always',
            autoClosingBrackets: 'always',
            autoClosingQuotes: 'always',
            formatOnPaste: true,
            formatOnType: true,
            suggest: { showKeywords: true },
            quickSuggestions: { other: true, comments: true, strings: true },
            parameterHints: { enabled: true },
            hover: { enabled: true },
            lightbulb: { enabled: true },
            codeActionsOnSave: { source: 'organizeImports' },
            tabSize: language === 'python' ? 4 : 2,
          }}
          className="h-full"
        />

        {!editorLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-950 z-10">
            <div className="animate-pulse space-y-2 text-slate-500">
              <div className="h-4 w-3/4 rounded bg-white/10" />
              <div className="h-4 w-1/2 rounded bg-white/10" />
            </div>
          </div>
        )}
      </div>

      <ResultPanel
        result={result}
        activeTab={activeResultTab}
        onTabChange={onResultTabChange}
        statusInfo={statusInfo}
      />
    </main>
  );
}

function ResultPanel({ result, activeTab, onTabChange, statusInfo }) {
  const tabs = [
    { id: 'testcases', label: 'Test Cases', icon: <Code className="w-4 h-4" /> },
    { id: 'output', label: 'Output', icon: <Terminal className="w-4 h-4" /> },
    { id: 'errors', label: 'Errors', icon: <Bug className="w-4 h-4" /> },
  ];

  if (!result?.raw) {
    return (
      <div className="border-t border-white/10 bg-slate-950/50">
        <div className="flex items-center gap-1 border-b border-white/10 px-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex items-center gap-2 px-3 py-2 text-xs font-medium uppercase tracking-[0.2em] transition ${
                activeTab === tab.id
                  ? 'text-cyan-300 border-b-2 border-cyan-400'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
        <div className="p-6 text-center text-slate-400">
          <Zap className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Run your code to see results here</p>
        </div>
      </div>
    );
  }

  const raw = result.raw;
  const isRunResult = raw.test_case_results && Array.isArray(raw.test_case_results);

  return (
    <div className="border-t border-white/10 bg-slate-950/50 min-h-[200px] max-h-[40vh] flex flex-col">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 bg-slate-950/80">
        <div className="flex items-center gap-2">
          {statusInfo && (
            <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase tracking-[0.2em] ${
              statusInfo.type === 'success'
                ? 'bg-emerald-400/10 border border-emerald-400/30 text-emerald-300'
                : 'bg-red-400/10 border border-red-400/30 text-red-300'
            }`}>
              {statusInfo.icon} {statusInfo.label}
            </span>
          )}
          {raw.test_cases_passed !== undefined && (
            <span className="text-sm text-slate-300">
              Tests: <span className="font-semibold text-white">{raw.test_cases_passed} / {raw.total_test_cases}</span>
            </span>
          )}
          {raw.score !== undefined && raw.score !== null && (
            <span className="text-sm text-slate-300">
              Score: <span className="font-semibold text-white">{Math.round(raw.score * 100)}%</span>
            </span>
          )}
          {raw.execution_time !== undefined && (
            <span className="text-sm text-slate-300">
              Time: <span className="font-semibold text-white">{raw.execution_time}s</span>
            </span>
          )}
          {raw.memory_used !== undefined && (
            <span className="text-sm text-slate-300">
              Memory: <span className="font-semibold text-white">{Math.round(raw.memory_used / 1024)} MB</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {tabs.map((tab) => {
            if (tab.id === 'testcases' && !isRunResult) return null;
            if (tab.id === 'errors' && !raw.compile_output && !raw.stderr && !raw.message) return null;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.2em] rounded-lg transition ${
                  activeTab === tab.id
                    ? 'bg-white/5 text-cyan-300'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'testcases' && isRunResult && (
          <TestCasesView testCases={raw.test_case_results} />
        )}
        {activeTab === 'output' && (
          <OutputView raw={raw} isRunResult={isRunResult} />
        )}
        {activeTab === 'errors' && (
          <ErrorsView raw={raw} />
        )}
      </div>
    </div>
  );
}

function TestCasesView({ testCases }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-white/10">
      <table className="w-full text-xs text-slate-200">
        <thead className="border-b border-white/10 bg-white/5 text-[11px] uppercase tracking-[0.2em] text-slate-400">
          <tr>
            <th className="px-3 py-2 text-left">#</th>
            <th className="px-3 py-2 text-left">Input</th>
            <th className="px-3 py-2 text-left">Expected</th>
            <th className="px-3 py-2 text-left">Actual</th>
            <th className="px-3 py-2 text-left">Status</th>
          </tr>
        </thead>
        <tbody>
          {testCases.map((tc, idx) => (
            <tr key={idx} className={`border-b border-white/5 ${tc.passed ? 'bg-emerald-950/20' : 'bg-red-950/20'}`}>
              <td className="px-3 py-2 text-slate-400">{idx + 1}</td>
              <td className="max-w-[150px] truncate px-3 py-2 font-mono">{tc.input_data}</td>
              <td className="max-w-[150px] truncate px-3 py-2 font-mono">{tc.expected_output}</td>
              <td className="max-w-[150px] truncate px-3 py-2 font-mono">{tc.actual_output || '(empty)'}</td>
              <td className="px-3 py-2">
                {tc.passed ? (
                  <span className="text-emerald-400 font-semibold">✓ Pass</span>
                ) : (
                  <span className="text-red-400 font-semibold">✗ Fail</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OutputView({ raw }) {
  return (
    <div className="space-y-3 font-mono text-xs leading-5">
      {raw.stdout && (
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-[0.15em] text-emerald-300">Stdout</span>
          </div>
          <pre className="text-emerald-100 whitespace-pre-wrap overflow-auto">{raw.stdout}</pre>
        </div>
      )}
      {raw.compile_output && (
        <div className="rounded-xl border border-red-400/30 bg-red-400/10 p-3">
          <div className="text-xs font-semibold text-red-300 mb-1">Compilation Output</div>
          <pre className="text-red-200 whitespace-pre-wrap overflow-auto">{raw.compile_output}</pre>
        </div>
      )}
      {!raw.stdout && !raw.compile_output && !raw.stderr && !raw.message && (
        <p className="text-slate-400 text-center py-8">No output generated</p>
      )}
    </div>
  );
}

function ErrorsView({ raw }) {
  return (
    <div className="space-y-3">
      {raw.stderr && (
        <div className="rounded-xl border border-orange-400/30 bg-orange-400/10 p-3">
          <div className="text-xs font-semibold text-orange-300 mb-1">Runtime Error (stderr)</div>
          <pre className="text-xs text-orange-200 font-mono whitespace-pre-wrap overflow-auto">{raw.stderr}</pre>
        </div>
      )}
      {raw.message && (
        <div className="rounded-xl border border-yellow-400/30 bg-yellow-400/10 p-3">
          <div className="text-xs font-semibold text-yellow-300 mb-1">Judge0 Message</div>
          <pre className="text-xs text-yellow-200 font-mono whitespace-pre-wrap overflow-auto">{raw.message}</pre>
        </div>
      )}
      {raw.compile_output && (
        <div className="rounded-xl border border-red-400/30 bg-red-400/10 p-3">
          <div className="text-xs font-semibold text-red-300 mb-1">Compilation Error</div>
          <pre className="text-xs text-red-200 font-mono whitespace-pre-wrap overflow-auto">{raw.compile_output}</pre>
        </div>
      )}
      {!raw.stderr && !raw.message && !raw.compile_output && (
        <p className="text-slate-400 text-center py-8">No errors</p>
      )}
    </div>
  );
}