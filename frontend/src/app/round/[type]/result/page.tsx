"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { CheckCircle2, ArrowRight, Loader2 } from "lucide-react";
import { ScoreRing } from "@/components/dashboard/ScoreRing";
import { useSessionStore } from "@/store/sessionStore";
import { MOCK_SESSION } from "@/lib/mockData";
import API from "@/lib/api";

interface PageProps {
  params: Promise<{
    type: string;
  }>;
}

interface SessionResult {
  round_id: number;
  status: string;
  total_score: number;
  problems_attempted: number;
  problems_solved: number;
}

export default function RoundResultPage(props: PageProps) {
  const params = use(props.params);
  const router = useRouter();
  const { activeRoundId } = useSessionStore();

  const type = params.type;

  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<SessionResult | null>(null);

  useEffect(() => {
    if (type === "coding" && activeRoundId) {
      API.get(`/coding/session/${activeRoundId}/result`)
        .then((res) => setResult(res.data))
        .catch(() => {
          // Fallback to mock
          const mockRound = MOCK_SESSION.rounds.find(r => r.round_type === type);
          if (mockRound) {
            setResult({
              round_id: mockRound.id,
              status: "completed",
              total_score: mockRound.score,
              problems_attempted: 3,
              problems_solved: 2,
            });
          }
        })
        .finally(() => setLoading(false));
    } else {
      // Non-coding or no round_id — use mock
      const mockRound = MOCK_SESSION.rounds.find(r => r.round_type === type);
      setResult({
        round_id: 0,
        status: "completed",
        total_score: mockRound?.score ?? 0,
        problems_attempted: 0,
        problems_solved: 0,
      });
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleContinue = () => {
    router.push("/dashboard");
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-surface items-center justify-center p-6">
      <div className="w-full max-w-lg rounded-3xl border border-gray-100 bg-white p-8 md:p-12 shadow-xl shadow-gray-200/20 text-center">

        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-teal-50 text-teal-500">
          <CheckCircle2 className="h-10 w-10" />
        </div>

        <h1 className="font-heading text-3xl font-extrabold text-heading mb-2">
          Round Completed!
        </h1>
        <p className="text-muted-foreground mb-8">
          You have successfully finished the {type} section. Your responses have been recorded.
        </p>

        <div className="flex justify-center mb-8">
          <ScoreRing score={result?.total_score ?? 0} size="lg" />
        </div>

        {result && type === "coding" && (
          <div className="flex justify-center gap-8 mb-8 text-sm">
            <div>
              <p className="text-muted-foreground">Total Problems</p>
              <p className="font-heading text-2xl font-bold text-heading">{result.problems_attempted}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Problems Solved</p>
              <p className="font-heading text-2xl font-bold text-teal-600">{result.problems_solved}</p>
            </div>
          </div>
        )}

        <Button
          size="lg"
          onClick={handleContinue}
          className="w-full h-14 bg-accent text-white hover:bg-accent/90 focus:ring-4 focus:ring-accent/20 transition-all text-base"
        >
          Return to Dashboard
          <ArrowRight className="ml-2 h-5 w-5" />
        </Button>

      </div>
    </div>
  );
}
