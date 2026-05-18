"use client";

import { Problem } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import ReactMarkdown from "react-markdown";
import { ChevronDown, ChevronRight, Bookmark } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface ProblemDescriptionProps {
  problem: Problem;
  isMarked: boolean;
  onToggleBookmark: () => void;
}

export function ProblemDescription({ problem, isMarked, onToggleBookmark }: ProblemDescriptionProps) {
  const [expandedCases, setExpandedCases] = useState<string[]>([]);

  const toggleCase = (id: string) => {
    setExpandedCases((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const difficultyColors = {
    easy: "bg-teal-900/40 text-teal-400",
    medium: "bg-amber-900/40 text-amber-400",
    hard: "bg-red-900/40 text-red-400",
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-[#1a1a1a] p-8 text-gray-300">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-3">
        <h2 className="font-heading text-2xl font-bold text-white">
          {problem.title}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={cn("hover:bg-transparent font-semibold border-transparent", difficultyColors[problem.difficulty])} variant="outline">
            {problem.difficulty.charAt(0).toUpperCase() + problem.difficulty.slice(1)}
          </Badge>
          {problem.tags.map((tag) => (
            <Badge key={tag} className="bg-white/10 text-gray-300 border-transparent hover:bg-white/20 transition-colors" variant="outline">
              {tag}
            </Badge>
          ))}
        </div>
      </div>

      {/* Description Body */}
      <div className="prose prose-sm prose-invert max-w-none prose-p:text-gray-300 prose-code:text-gray-200 prose-code:bg-white/10 prose-code:px-1 prose-code:rounded">
        <ReactMarkdown>{problem.description}</ReactMarkdown>
      </div>

      <div className="my-8 h-px w-full bg-gray-800" />

      {/* Constraints & Format */}
      <div className="mb-8 space-y-6">
        <Section title="Input Format" content={problem.input_format} />
        <Section title="Output Format" content={problem.output_format} />
        <Section title="Constraints" content={problem.constraints} />
      </div>

      {/* Examples */}
      <div className="mb-8 space-y-4">
        <h3 className="font-heading text-base font-bold text-white uppercase tracking-wider">Examples</h3>
        {problem.examples.map((ex, idx) => (
          <div key={idx} className="overflow-hidden rounded-xl border border-gray-800">
            <div className="bg-[#242424] px-4 py-2 border-b border-gray-800 font-mono text-xs font-semibold text-gray-400">
              Example {idx + 1}
            </div>
            <div className="bg-[#1e1e1e] p-5 text-[13px] font-mono text-[#98C0E8]">
              <div className="mb-4">
                <span className="text-gray-500 mr-4 select-none">Input :</span>
                {ex.input.split("\n").map((line, i) => (
                  <div key={i} className={i > 0 ? "ml-[60px]" : "inline"}>{line}</div>
                ))}
              </div>
              <div className="mb-4">
                <span className="text-gray-500 mr-4 select-none">Output:</span>
                <span>{ex.output}</span>
              </div>
              {ex.explanation && (
                <div className="text-gray-400">
                  <span className="text-gray-500 mr-4 select-none">Explain:</span>
                  <span>{ex.explanation}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Visible Test Cases Accordion */}
      <div className="mb-16 space-y-4">
        <h3 className="font-heading text-base font-bold text-white uppercase tracking-wider">Visible Test Cases</h3>
        <div className="space-y-2">
          {problem.visible_test_cases.map((tc, idx) => {
            const isExpanded = expandedCases.includes(tc.id);
            return (
              <div key={tc.id} className="overflow-hidden rounded-lg border border-gray-800 bg-[#1e1e1e]">
                <button
                  onClick={() => toggleCase(tc.id)}
                  className="flex w-full items-center justify-between bg-[#242424] px-4 py-3 hover:bg-[#2a2a2a]"
                >
                  <span className="font-medium text-sm text-gray-300">Test Case {idx + 1}</span>
                  {isExpanded ? <ChevronDown className="h-4 w-4 text-gray-500" /> : <ChevronRight className="h-4 w-4 text-gray-500" />}
                </button>
                {isExpanded && (
                  <div className="bg-[#1e1e1e] p-4 text-xs font-mono text-[#98C0E8] flex gap-8">
                    <div className="flex-1">
                      <div className="mb-2 text-gray-500 uppercase tracking-widest text-[10px]">Input</div>
                      <pre className="m-0 whitespace-pre-wrap">{tc.input_data}</pre>
                    </div>
                    <div className="flex-1">
                      <div className="mb-2 text-gray-500 uppercase tracking-widest text-[10px]">Expected Output</div>
                      <pre className="m-0 whitespace-pre-wrap">{tc.expected_output}</pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom Sticky Action Bar */}
      <div className="sticky bottom-0 -mx-8 -mb-8 mt-auto flex items-center justify-between border-t border-gray-800 bg-[#1a1a1a]/95 px-8 py-4 backdrop-blur-sm">
        <button
          onClick={onToggleBookmark}
          className="flex items-center gap-2 text-sm font-medium transition-colors hover:text-white text-gray-400"
        >
          <Bookmark className="h-4 w-4" fill={isMarked ? "currentColor" : "none"} />
          {isMarked ? "Marked for Review" : "Mark for Review"}
        </button>
        <button className="text-sm font-medium text-gray-500 hover:text-gray-300 underline underline-offset-4">
          View History
        </button>
      </div>
    </div>
  );
}

function Section({ title, content }: { title: string; content: string }) {
  if (!content) return null;
  return (
    <div className="border-l-4 border-gray-600 pl-4">
      <h3 className="mb-2 font-heading text-sm font-bold tracking-wide text-gray-200 uppercase">{title}</h3>
      <div className="prose prose-sm prose-invert max-w-none prose-code:text-gray-200 prose-code:bg-white/10 prose-code:px-1 prose-code:rounded text-gray-400">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
