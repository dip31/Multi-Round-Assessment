"use client";

import { MOCK_SESSION, MOCK_USER } from "@/lib/mockData";
import { ScoreRing } from "@/components/dashboard/ScoreRing";
import { CheckCircle2, Trophy, BarChart, ArrowRight, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

export default function FinalResultsPage() {
  const router = useRouter();
  
  // Fake aggregate logic
  const totalScore = Math.floor(MOCK_SESSION.rounds.reduce((acc, r) => acc + r.score, 0) / 3);
  const isPassed = totalScore >= 60;

  return (
    <div className="min-h-screen bg-surface p-6 md:p-12">
      <div className="mx-auto max-w-4xl space-y-8">
        
        {/* Header Block */}
        <div className="flex flex-col items-center text-center space-y-4 pt-8 pb-12">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-accent/10 text-accent mb-2">
            <Trophy className="h-10 w-10" />
          </div>
          <h1 className="font-heading text-4xl font-extrabold text-heading">
            Placement Readiness Report
          </h1>
          <p className="text-lg text-muted-foreground max-w-xl">
            Congratulations on completing all rounds, {MOCK_USER.name}! Here is your detailed performance breakdown.
          </p>
        </div>

        {/* Aggregate Score Card */}
        <div className="rounded-3xl border border-gray-100 bg-white p-8 md:p-12 shadow-xl shadow-gray-200/10 flex flex-col md:flex-row items-center gap-12">
          
          <div className="shrink-0 flex flex-col items-center">
             <ScoreRing score={totalScore} size="lg" />
             <div className="mt-4">
               {isPassed ? (
                 <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-4 py-1.5 text-sm font-semibold text-teal-700">
                   <CheckCircle2 className="h-4 w-4" /> Ready for Interviews
                 </span>
               ) : (
                 <span className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-4 py-1.5 text-sm font-semibold text-amber-700">
                   <BarChart className="h-4 w-4" /> Needs Improvement
                 </span>
               )}
             </div>
          </div>

          <div className="flex-1 space-y-6 w-full">
            <h3 className="text-2xl font-bold text-heading font-heading mb-4">Round Breakdown</h3>
            
            <div className="space-y-4 w-full">
              {MOCK_SESSION.rounds.map((round) => (
                <div key={round.id} className="flex items-center gap-4">
                  <div className="w-24 font-semibold capitalize text-heading">{round.round_type}</div>
                  <div className="flex-1 h-3 rounded-full bg-gray-100 overflow-hidden relative">
                    <div 
                      className={cn(
                        "absolute inset-y-0 left-0 transition-all duration-1000",
                        round.score >= 70 ? "bg-teal-500" : round.score >= 40 ? "bg-amber-400" : "bg-red-400"
                      )}
                      style={{ width: `${round.score}%` }}
                    />
                  </div>
                  <div className="w-12 text-right font-mono font-bold text-gray-700">{round.score}%</div>
                </div>
              ))}
            </div>

          </div>
        </div>

        <div className="flex justify-center pt-8">
          <Button 
            size="lg" 
            onClick={() => router.push("/dashboard")}
            className="h-14 px-8"
            variant="outline"
          >
            <Home className="mr-2 h-5 w-5" />
            Back to Dashboard
          </Button>
        </div>

      </div>
    </div>
  );
}
