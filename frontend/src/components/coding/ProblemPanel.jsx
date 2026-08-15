import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Copy, CheckCircle, AlertCircle, Info } from 'lucide-react';

const DIFFICULTY_STYLES = {
  easy: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
  medium: 'border-yellow-400/30 bg-yellow-400/10 text-yellow-300',
  hard: 'border-red-400/30 bg-red-400/10 text-red-300',
};

function formatText(text) {
  if (!text) return '';
  return String(text)
    .replace(/<[^>]+>/g, '')
    .replace(/\r\n/g, '\n')
    .trim();
}

function renderMultiline(text) {
  if (!text) return null;
  const lines = formatText(text).split('\n');
  return lines.map((line, i) => (
    <p key={i} className="leading-7 whitespace-pre-wrap">{line || '\u00A0'}</p>
  ));
}

function DifficultyBadge({ difficulty }) {
  const style = DIFFICULTY_STYLES[difficulty?.toLowerCase()] || DIFFICULTY_STYLES.easy;
  return (
    <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${style}`}>
      {difficulty || 'Easy'}
    </span>
  );
}

function Section({ title, icon, children, className = '' }) {
  const [isOpen, setIsOpen] = useState(true);
  return (
    <div className={`rounded-2xl border border-white/10 bg-white/5 overflow-hidden ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between gap-3 p-4 text-left"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          {icon && <span className="text-slate-400">{icon}</span>}
          <h5 className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">{title}</h5>
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
      </button>
      {isOpen && (
        <div className="px-4 pb-4 border-t border-white/10">
          {children}
        </div>
      )}
    </div>
  );
}

function ExampleBlock({ example, index }) {
  return (
    <div className="space-y-3 rounded-xl border border-white/10 bg-slate-950/50 p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Example {index + 1}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-[0.15em] text-slate-500">Input</span>
            <button className="p-1 rounded hover:bg-white/10 transition" aria-label="Copy input">
              <Copy className="w-3 h-3 text-slate-500" />
            </button>
          </div>
          <pre className="text-xs leading-5 font-mono text-slate-200 overflow-auto whitespace-pre-wrap">
            {formatText(example.input)}
          </pre>
        </div>
        <div className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-[0.15em] text-slate-500">Output</span>
            <button className="p-1 rounded hover:bg-white/10 transition" aria-label="Copy output">
              <Copy className="w-3 h-3 text-slate-500" />
            </button>
          </div>
          <pre className="text-xs leading-5 font-mono text-slate-200 overflow-auto whitespace-pre-wrap">
            {formatText(example.output)}
          </pre>
        </div>
      </div>
      {example.explanation && (
        <div className="rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-3">
          <div className="flex items-center gap-2 text-xs text-cyan-200 mb-1">
            <Info className="w-3 h-3" />
            <span className="font-semibold uppercase tracking-[0.15em]">Explanation</span>
          </div>
          <p className="text-xs leading-6 text-cyan-100">{formatText(example.explanation)}</p>
        </div>
      )}
    </div>
  );
}

function ConstraintList({ constraints }) {
  if (!constraints || !constraints.length) return null;
  
  const constraintArray = typeof constraints === 'string' 
    ? constraints.split('\n').filter(Boolean)
    : constraints;

  return (
    <div className="space-y-2">
      {constraintArray.map((constraint, idx) => (
        <div key={idx} className="flex items-start gap-3 text-sm leading-6 text-slate-200">
          <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
          <span>{formatText(constraint).replace(/^[•\-*]\s*/, '')}</span>
        </div>
      ))}
    </div>
  );
}

export default function ProblemPanel({ problem }) {
  const examples = useMemo(() => {
    if (!problem) return [];
    if (problem.examples) {
      if (Array.isArray(problem.examples)) return problem.examples;
      if (typeof problem.examples === 'string') {
        try {
          const parsed = JSON.parse(problem.examples);
          return Array.isArray(parsed) ? parsed : [];
        } catch {
          return [];
        }
      }
    }
    // The backend exposes visible test cases as CodingTestCaseResponse entries with
    // input_data / expected_output / explanation. Use them as the examples section
    // rather than hardcoding anything.
    if (Array.isArray(problem.test_cases)) {
      return problem.test_cases
        .filter((tc) => !tc.is_hidden)
        .map((tc) => ({
          input: tc.input_data,
          output: tc.expected_output,
          explanation: tc.explanation,
        }));
    }
    return [];
  }, [problem]);

  const constraints = useMemo(() => {
    if (!problem?.constraints) return [];
    if (Array.isArray(problem.constraints)) return problem.constraints;
    if (typeof problem.constraints === 'string') {
      try {
        const parsed = JSON.parse(problem.constraints);
        return Array.isArray(parsed) ? parsed : problem.constraints.split('\n').filter(Boolean);
      } catch {
        return problem.constraints.split('\n').filter(Boolean);
      }
    }
    return [];
  }, [problem?.constraints]);

  if (!problem) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center text-slate-400">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No problem selected</p>
        </div>
      </div>
    );
  }

  return (
    <aside className="flex flex-col h-full overflow-hidden border-r border-white/10 bg-slate-950/50">
      <div className="flex h-full flex-col">
        <div className="border-b border-white/10 px-6 py-5 flex-shrink-0">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
            <div className="min-w-0">
              <h3 className="text-xl font-bold text-white truncate">{problem.title}</h3>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <DifficultyBadge difficulty={problem.difficulty} />
                {(problem.tags || []).slice(0, 3).map((tag) => (
                  <span key={tag} className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-400">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
          
          {problem.input_format && (
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <h5 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500 mb-1">Input Format</h5>
              <p className="text-xs text-slate-300">{formatText(problem.input_format)}</p>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <Section title="Problem Description" icon={<Info className="w-3 h-3" />}>
            <div className="whitespace-pre-wrap text-sm leading-7 text-slate-200">
              {renderMultiline(problem.description)}
            </div>
          </Section>

          {examples.length > 0 && (
            <Section title="Examples" icon={<CheckCircle className="w-3 h-3" />}>
              <div className="space-y-4">
                {examples.map((example, idx) => (
                  <ExampleBlock key={idx} example={example} index={idx} />
                ))}
              </div>
            </Section>
          )}

          {constraints.length > 0 && (
            <Section title="Constraints" icon={<AlertCircle className="w-3 h-3" />}>
              <ConstraintList constraints={constraints} />
            </Section>
          )}

          {problem.output_format && (
            <Section title="Output Format" icon={<Info className="w-3 h-3" />}>
              <p className="text-sm leading-6 text-slate-200 whitespace-pre-wrap">{formatText(problem.output_format)}</p>
            </Section>
          )}

          {problem.follow_up && (
            <Section title="Follow-up" icon={<Info className="w-3 h-3" />} className="border-cyan-400/20 bg-cyan-400/5">
              <p className="text-sm leading-6 text-cyan-100 whitespace-pre-wrap">{formatText(problem.follow_up)}</p>
            </Section>
          )}
        </div>
      </div>
    </aside>
  );
}