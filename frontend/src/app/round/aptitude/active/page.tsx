"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/shared/Toast";
import { CountdownTimer } from "@/components/coding/CountdownTimer";
import { EndRoundButton } from "@/components/coding/EndRoundButton";
import { MCQQuestion } from "@/components/aptitude/MCQQuestion";
import { AptitudeStats } from "@/components/aptitude/AptitudeStats";
import { MOCK_APTITUDE_QUESTIONS } from "@/lib/mockAptitudeData";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export default function ActiveAptitudeRoundPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  
  const currentQuestion = MOCK_APTITUDE_QUESTIONS[currentIndex];
  const totalQuestions = MOCK_APTITUDE_QUESTIONS.length;
  const answeredCount = Object.keys(answers).length;

  const handleOptionSelect = (optionId: string) => {
    setAnswers((prev) => ({
      ...prev,
      [currentQuestion.id]: optionId,
    }));
  };

  const handleNext = () => {
    if (currentIndex < totalQuestions - 1) {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const handleEndRound = () => {
    toast({
      title: "Round Ended",
      description: "Your aptitude test has been submitted successfully.",
    });
    router.push("/dashboard");
  };

  const handleTimerExpire = () => {
    toast({
      title: "Time's Up",
      description: "Submissions are now closed. Redirecting...",
      variant: "destructive"
    });
    setTimeout(() => {
      router.push("/dashboard");
    }, 3000);
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-surface">
      {/* Header Bar */}
      <header className="sticky top-0 z-50 flex h-16 w-full shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-heading text-lg font-bold text-heading">Aptitude Round</span>
        </div>

        <div className="absolute left-1/2 -translate-x-1/2">
           <CountdownTimer
            initialSeconds={1800} // 30 mins mock
            onExpire={handleTimerExpire}
          />
        </div>

        <EndRoundButton onEndRound={handleEndRound} />
      </header>

      {/* Main Content */}
      <main className="flex flex-1 overflow-hidden p-6 md:p-8">
        <div className="mx-auto flex w-full max-w-6xl gap-8 relative h-full">
          
          {/* Question Pane */}
          <div className="flex flex-1 flex-col overflow-hidden relative">
            <div className="flex-1 overflow-y-auto pb-24">
              <MCQQuestion
                questionNumber={currentIndex + 1}
                totalQuestions={totalQuestions}
                questionText={currentQuestion.questionText}
                options={currentQuestion.options}
                selectedOptionId={answers[currentQuestion.id]}
                onOptionSelect={handleOptionSelect}
              />
            </div>

            {/* Bottom Navigation */}
            <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between border-t border-gray-100 bg-white/80 p-4 backdrop-blur-md rounded-b-2xl">
              <button
                onClick={handlePrev}
                disabled={currentIndex === 0}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-4 py-2 font-medium transition-all text-sm",
                  currentIndex === 0 ? "text-gray-300 cursor-not-allowed" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <ChevronLeft className="h-5 w-5" />
                Previous
              </button>
              
              {currentIndex === totalQuestions - 1 ? (
                <button
                  onClick={handleEndRound}
                  className="flex items-center gap-2 rounded-lg bg-accent px-8 py-2 font-semibold text-white shadow-sm transition-all hover:bg-accent/90 focus:ring-4 focus:ring-accent/20 active:scale-95"
                >
                  Submit Test
                </button>
              ) : (
                <button
                  onClick={handleNext}
                  className="flex items-center gap-2 rounded-lg bg-gray-900 px-6 py-2 font-medium text-white transition-all hover:bg-gray-800 focus:ring-4 focus:ring-gray-200"
                >
                  Next
                  <ChevronRight className="h-5 w-5" />
                </button>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="hidden w-[320px] shrink-0 flex-col gap-6 lg:flex overflow-y-auto">
            <AptitudeStats answeredCount={answeredCount} totalCount={totalQuestions} />

            {/* Question Navigator Grid */}
            <div className="flex flex-col gap-4 rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
              <h3 className="font-heading text-sm font-bold text-heading uppercase tracking-wider text-center">Navigator</h3>
              <div className="grid grid-cols-5 gap-2">
                {MOCK_APTITUDE_QUESTIONS.map((q, idx) => {
                  const isAnswered = !!answers[q.id];
                  const isCurrent = currentIndex === idx;

                  return (
                    <button
                      key={q.id}
                      onClick={() => setCurrentIndex(idx)}
                      className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold transition-all",
                        isCurrent && "ring-2 ring-accent ring-offset-2",
                        isAnswered && !isCurrent ? "bg-teal-500 text-white" : "",
                        !isAnswered && !isCurrent ? "bg-gray-100 text-gray-500 hover:bg-gray-200" : "",
                        isCurrent && isAnswered ? "bg-teal-600 text-white" : "",
                        isCurrent && !isAnswered ? "bg-accent/10 text-accent" : ""
                      )}
                    >
                      {idx + 1}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
