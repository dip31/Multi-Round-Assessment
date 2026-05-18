"use client";

import { useCodePersist } from "@/hooks/useCodePersist";
import { LANGUAGE } from "@/lib/constants";
import { LoadingSkeleton } from "../shared/LoadingSkeleton";
import { Maximize2, RotateCcw, Play } from "lucide-react";
import dynamic from "next/dynamic";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

// Lazily load Monaco Editor so it doesn't block the main JS thread
const MonacoEditor = dynamic(() => import("@monaco-editor/react").then((mod) => mod.Editor), {
  ssr: false,
  loading: () => <LoadingSkeleton className="h-full w-full bg-[#0D1117]" />,
});

const DEFAULT_CODE: Record<string, string> = {
  [LANGUAGE.PYTHON]: "def solution():\n    pass\n",
  [LANGUAGE.CPP]: "#include<bits/stdc++.h>\nusing namespace std;\nint main(){\n    return 0;\n}",
  [LANGUAGE.JAVA]: "import java.util.*;\npublic class Solution {\n    public static void main(String[] args) {\n    }\n}",
};

interface CodeEditorProps {
  problemId: number;
  language: string;
  onLanguageChange: (lang: string) => void;
  onRun: (code: string) => void;
  onSubmit: (code: string) => void;
  isSubmitting?: boolean;
  submitDisabled?: boolean;
}

export function CodeEditor({
  problemId,
  language,
  onLanguageChange,
  onRun,
  onSubmit,
  isSubmitting,
  submitDisabled,
}: CodeEditorProps) {
  const { code, setCode } = useCodePersist(problemId, language);
  const [fontSize, setFontSize] = useState(14);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // When switching problems or languages, ensure there is at least the default code
  useEffect(() => {
    if (!code) {
      setCode(DEFAULT_CODE[language] || "");
    }
  }, [code, language, setCode]);

  const handleReset = () => {
    if (confirm("Reset current code to the default template? You will lose any changes.")) {
      setCode(DEFAULT_CODE[language] || "");
    }
  };

  return (
    <div className={cn("flex flex-col bg-[#0D1117] h-full", isFullscreen && "fixed inset-0 z-[100] h-screen w-screen")}>
      {/* Editor Toolbar */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-white/5 bg-[#161B22] px-4">
        
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            className="rounded bg-black/20 px-3 py-1 text-sm font-medium text-gray-300 outline-none hover:text-white focus:ring-1 focus:ring-accent"
          >
            <option value={LANGUAGE.PYTHON}>Python 3</option>
            <option value={LANGUAGE.CPP}>C++ 17</option>
            <option value={LANGUAGE.JAVA}>Java 11</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setFontSize((f) => Math.max(10, f - 1))}
            className="flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-white/10 hover:text-white"
            title="Decrease Font Size"
          >
            A-
          </button>
          <button
            onClick={() => setFontSize((f) => Math.min(24, f + 1))}
            className="flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-white/10 hover:text-white"
            title="Increase Font Size"
          >
            A+
          </button>
          <div className="mx-1 h-4 w-px bg-white/10" />
          <button
            onClick={handleReset}
            className="flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-white/10 hover:text-white"
            title="Reset to default template"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="flex h-7 w-7 items-center justify-center rounded text-gray-400 hover:bg-white/10 hover:text-white"
            title="Toggle Fullscreen"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Editor Area */}
      <div className="flex-grow overflow-hidden relative">
        <MonacoEditor
          key={`${problemId}-${language}`}
          height="100%"
          language={language}
          theme="vs-dark"
          value={code || DEFAULT_CODE[language]}
          onChange={(val) => setCode(val || "")}
          options={{
            fontSize: fontSize,
            fontFamily: "var(--font-mono), monospace",
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            padding: { top: 16, bottom: 16 },
            lineNumbersMinChars: 3,
            folding: true,
          }}
        />
        {/* Loading Overlay from Parent isSubmitting */}
        {isSubmitting && (
            <div className="absolute inset-x-0 top-0 h-1 z-50 overflow-hidden bg-accent/20">
                <div className="h-full w-full origin-left bg-accent animate-[indeterminate_1.5s_infinite_linear]" />
            </div>
        )}
      </div>

      {/* Bottom Action Bar */}
      <div className="flex h-14 shrink-0 items-center justify-end gap-3 border-t border-white/5 bg-[#161B22] px-4">
        <button
          onClick={() => onRun(code)}
          disabled={isSubmitting}
          className="flex h-9 items-center gap-2 rounded-md border border-teal-500/50 bg-transparent px-4 text-sm font-semibold text-teal-400 transition-colors hover:bg-teal-500/10 active:bg-teal-500/20 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          Run Code
        </button>
        <button
          onClick={() => onSubmit(code)}
          disabled={isSubmitting || submitDisabled}
          className="flex h-9 items-center justify-center rounded-md bg-accent px-6 text-[15px] font-semibold text-white shadow-sm transition-all hover:bg-accent/90 active:scale-95 disabled:pointer-events-none disabled:opacity-70"
        >
          {isSubmitting ? "Submitting..." : "Submit"}
        </button>
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes indeterminate {
            0% { transform: scaleX(0); transform-origin: left; }
            50% { transform: scaleX(1); transform-origin: left; }
            50.001% { transform: scaleX(1); transform-origin: right; }
            100% { transform: scaleX(0); transform-origin: right; }
        }
      `}} />
    </div>
  );
}
