"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Brain, Code2, AlertCircle, Clock, ShieldCheck, ArrowRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSessionStore } from "@/store/sessionStore";
import API from "@/lib/api";

interface PageProps {
  params: Promise<{
    type: string;
  }>;
}

export default function RoundGatePage(props: PageProps) {
  const params = use(props.params);
  const router = useRouter();
  const { setActiveRound } = useSessionStore();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const type = params.type;

  const content = {
    aptitude: {
      title: "Aptitude Round",
      icon: <Brain className="h-10 w-10 text-teal-500" />,
      theme: "teal",
      time: "30 Minutes",
      questions: 20,
      instructions: [
        "This section consists of 20 Multiple Choice Questions.",
        "You cannot pause the assessment once started.",
        "Ensure you have a stable internet connection.",
        "There is no negative marking for incorrect answers."
      ]
    },
    coding: {
      title: "Coding Round",
      icon: <Code2 className="h-10 w-10 text-amber-500" />,
      theme: "amber",
      time: "90 Minutes",
      questions: 3,
      instructions: [
        "This section consists of 3 algorithmic coding problems.",
        "You can code in Python, Java, C++, or JavaScript.",
        "All test cases must pass to get full score for a problem.",
        "Leaving full screen mode may terminate the session."
      ]
    }
  }[type as "aptitude" | "coding"];

  if (!content) {
    return <div className="p-8 text-center text-red-500">Invalid Round Type</div>;
  }

  const handleStart = async () => {
    if (type === "coding") {
      setStarting(true);
      setError(null);
      try {
        const response = await API.post("/coding/start-round");
        // Success: new round created
        const { round_id } = response.data;
        useSessionStore.getState().setActiveRound({
          roundId: round_id,
          roundType: "coding",
        });
        router.push("/round/coding/active");
      } catch (err: any) {
        if (err.response?.status === 400) {
          // Round already exists — resume it
          try {
            const sessionRes = await API.get("/session/status");
            const codingRound = sessionRes.data.rounds?.find(
              (r: any) =>
                r.round_type === "coding" &&
                (r.status === "active" || r.status === "in_progress")
            );
            if (codingRound) {
              useSessionStore.getState().setActiveRound({
                roundId: codingRound.id,
                roundType: "coding",
              });
              router.push("/round/coding/active");
              return;
            }
            setError("Could not resume coding round. Please refresh.");
          } catch {
            setError("Could not resume coding round. Please refresh.");
          }
        } else if (err.response?.status === 403) {
          setError("Please complete the Aptitude round first.");
          router.push("/dashboard");
        } else {
          setError("Could not start round. Please try again.");
        }
      } finally {
        setStarting(false);
      }
    } else {
      // Aptitude — navigate directly for now (stub)
      router.push(`/round/${type}/active`);
    }
  };

  return (
    <div className="flex min-h-screen bg-surface items-center justify-center p-6">
      <div className="mx-auto w-full max-w-3xl rounded-3xl border border-gray-100 bg-white p-8 md:p-12 shadow-xl shadow-gray-200/20">

        <div className="flex flex-col md:flex-row md:items-start gap-8">

          <div className={cn(
            "flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl",
            content.theme === "teal" ? "bg-teal-50" : "bg-amber-50"
          )}>
            {content.icon}
          </div>

          <div className="flex-1 space-y-6">
            <div>
              <h1 className="font-heading text-3xl font-extrabold text-heading md:text-4xl">
                {content.title}
              </h1>
              <p className="mt-2 text-lg text-muted-foreground">
                Read the instructions carefully before beginning your assessment.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 py-4 border-y border-gray-100">
              <div className="flex items-center gap-3">
                <div className="rounded-full bg-gray-100 p-2 text-gray-600">
                  <Clock className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">Time Limit</p>
                  <p className="font-bold text-heading">{content.time}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-full bg-gray-100 p-2 text-gray-600">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">Proctoring</p>
                  <p className="font-bold text-heading">Enabled</p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="flex items-center gap-2 font-semibold text-heading">
                <AlertCircle className="h-5 w-5 text-accent" />
                Important Instructions
              </h3>
              <ul className="space-y-3">
                {content.instructions.map((inst, i) => (
                  <li key={i} className="flex items-start gap-3 text-gray-600">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    <span className="leading-relaxed">{inst}</span>
                  </li>
                ))}
              </ul>
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 font-medium">
                {error}
              </div>
            )}

            <div className="pt-8">
              <Button
                size="lg"
                onClick={handleStart}
                disabled={starting}
                className="w-full sm:w-auto h-14 px-8 text-base shadow-lg shadow-accent/20 transition-all hover:-translate-y-1 disabled:opacity-70"
              >
                {starting ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    Start Assessment
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </>
                )}
              </Button>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
