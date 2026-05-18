"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/shared/Navbar";
import { RoundCard } from "@/components/dashboard/RoundCard";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { useAuth } from "@/hooks/useAuth";
import { useSessionStore } from "@/store/sessionStore";
import { Trophy, Target, Flag, Loader2 } from "lucide-react";
import API from "@/lib/api";

interface RoundData {
  id: number;
  session_id: number;
  round_type: string;
  status: string;
  score: number;
  max_questions: number;
  started_at: string | null;
  completed_at: string | null;
}

interface SessionData {
  id: number;
  user_id: number;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  total_score: number;
  rounds: RoundData[];
}

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, user, token } = useAuth();
  const { setSession, setActiveRound } = useSessionStore();
  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [session, setSessionData] = useState<SessionData | null>(null);
  const [noSession, setNoSession] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string>("Candidate");

  const fetchSession = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get("/session/status");
      const data: SessionData = res.data;
      setSessionData(data);
      setSession(data.id);
      setNoSession(false);
    } catch (err: any) {
      if (err.response?.status === 404 || err.response?.status === 400) {
        setNoSession(true);
        setSessionData(null);
      } else if (err.response?.status === 401) {
        router.replace("/login");
      } else {
        setError("Failed to load session. Please refresh.");
      }
    } finally {
      setLoading(false);
    }
  }, [router, setSession]);

  const startCodingRoundFromDashboard = useCallback(async () => {
    try {
      const res = await API.post("/coding/start-round");
      const { round_id } = res.data;
      setActiveRound(round_id, "coding");
      router.push("/round/coding/active");
    } catch (err: any) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;

      if (
        status === 400 &&
        typeof detail === "string" &&
        detail.toLowerCase().includes("already")
      ) {
        // Round already started — just go to active view
        router.push("/round/coding/active");
      } else if (status === 403) {
        // Previous round not completed or session invalid — stay on dashboard
        setError(
          detail || "Please complete the previous round before coding round."
        );
      } else if (status === 401) {
        router.push("/login");
      } else if (detail) {
        setError(detail);
      }
    }
  }, [router, setActiveRound]);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Derive display name from JWT token payload, falling back to stored user
  useEffect(() => {
    if (!mounted) return;

    if (token) {
      try {
        const [, payloadBase64] = token.split(".");
        const payloadJson = atob(payloadBase64);
        const payload = JSON.parse(payloadJson);

        let name: string =
          payload.name ??
          payload.sub ??
          user?.name ??
          "Candidate";

        if (typeof name === "string" && name.includes("@")) {
          name = name.split("@")[0];
        }

        setDisplayName(name);
      } catch {
        setDisplayName(user?.name || "Candidate");
      }
    } else {
      setDisplayName(user?.name || "Candidate");
    }
  }, [token, user, mounted]);

  useEffect(() => {
    if (mounted) {
      fetchSession();
    }
  }, [mounted, fetchSession]);

  const handleBeginAssessment = async () => {
    try {
      setCreating(true);
      await API.post("/session/start");
      // Re-fetch session — now rounds[] will be populated
      await fetchSession();
      // Immediately start coding round so candidate can begin coding
      await startCodingRoundFromDashboard();
      setNoSession(false);
    } catch (err: any) {
      if (err.response?.status === 409) {
        // Session already exists — re-fetch and try to start coding round
        await fetchSession();
        await startCodingRoundFromDashboard();
      } else {
        setError("Failed to create session. Please try again.");
      }
    } finally {
      setCreating(false);
    }
  };

  const handleRoundClick = (roundId: number, type: string) => {
    router.push(`/round/${type}`);
  };

  if (!mounted) return null;

  // Derive stats
  const rounds = session?.rounds || [];
  const completedRounds =
    session?.rounds?.filter((r) => r.status === "completed").length ?? 0;
  const totalScore = session?.total_score ?? 0;
  const bestRound =
    session?.rounds
      ?.filter((r) => r.status === "completed")
      ?.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0] ?? null;
  const progressWidth = totalScore;

  const LoadingSkeleton = () => (
    <div className="flex flex-col items-center justify-center gap-4 py-20">
      <Loader2 className="h-8 w-8 animate-spin text-accent" />
      <p className="text-muted-foreground">Loading your session...</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface">
      <Navbar />

      {/* Hero Header */}
      <div className="w-full bg-heading px-6 py-10 text-white">
        <div className="mx-auto max-w-6xl">
          <h1 className="font-heading text-3xl font-bold md:text-4xl">
            Welcome back, {displayName}
          </h1>

          {session && (
            <div className="mt-8 flex flex-col gap-3">
              <div className="flex items-center justify-between text-sm font-semibold">
                <span className="text-white/80">Assessment Progress</span>
                <span className="text-accent-300">{totalScore}%</span>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-accent transition-all duration-1000 ease-out"
                  style={{ width: `${progressWidth}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="mx-auto max-w-6xl px-6 py-12">

        {loading && <LoadingSkeleton />}

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-red-600 font-medium">{error}</p>
            <button onClick={fetchSession} className="mt-4 rounded-lg bg-red-600 px-6 py-2 text-white text-sm font-semibold hover:bg-red-700">
              Retry
            </button>
          </div>
        )}

        {!loading && noSession && (
          <div className="flex flex-col items-center py-16">
            <p className="text-gray-500 mb-6">
              You have not started your assessment yet.
            </p>
            <button
              onClick={handleBeginAssessment}
              disabled={creating}
              className="bg-[#6C63FF] text-white px-8 py-3 rounded-lg font-semibold hover:scale-105 transition-transform disabled:opacity-70"
            >
              {creating ? "Creating Session..." : "Begin Assessment"}
            </button>
          </div>
        )}

        {!loading && session && session.rounds && session.rounds.length > 0 && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {session.rounds.map((round) => (
              <RoundCard key={round.id} round={round} />
            ))}
          </div>
        )}

        {!loading &&
          session &&
          (!session.rounds || session.rounds.length === 0) &&
          !noSession && (
            <div className="flex flex-col items-center py-16">
              <p className="text-gray-500 mb-6">
                Session found but no rounds available.
              </p>
              <button
                onClick={handleBeginAssessment}
                disabled={creating}
                className="bg-[#6C63FF] text-white px-8 py-3 rounded-lg font-semibold hover:scale-105 transition-transform disabled:opacity-70"
              >
                {creating ? "Initializing..." : "Initialize Rounds"}
              </button>
            </div>
          )}

        {session && !loading && (
          <div className="mt-12 flex flex-col gap-8 lg:flex-row">
            <div className="w-full lg:w-[60%]">
              <ActivityFeed />
            </div>

            <div className="w-full lg:w-[40%]">
              <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm h-full">
                <h3 className="mb-6 font-heading text-lg font-bold text-heading text-center">
                  Quick Stats
                </h3>

                <div className="space-y-6 flex flex-col items-center">
                  <div className="flex items-center gap-4 w-full justify-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent">
                      <Trophy className="h-6 w-6" />
                    </div>
                    <div className="w-32">
                      <p className="text-sm font-medium text-muted-foreground justify-center flex">
                        Total Score
                      </p>
                      <p className="font-heading text-xl font-bold text-heading justify-center flex">
                        {totalScore}/100
                      </p>
                    </div>
                  </div>

                  <div className="h-px w-3/4 bg-gray-100" />

                  <div className="flex items-center gap-4 w-full justify-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
                      <Target className="h-6 w-6" />
                    </div>
                    <div className="w-32">
                      <p className="text-sm font-medium text-muted-foreground justify-center flex">
                        Rounds
                      </p>
                      <p className="font-heading text-xl font-bold text-heading justify-center flex">
                        {completedRounds} / 3 done
                      </p>
                    </div>
                  </div>

                  <div className="h-px w-3/4 bg-gray-100" />

                  <div className="flex items-center gap-4 w-full justify-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                      <Flag className="h-6 w-6" />
                    </div>
                    <div className="w-32">
                      <p className="text-sm font-medium text-muted-foreground justify-center flex">
                        Best
                      </p>
                      <p className="font-heading text-lg font-bold text-heading justify-center flex tracking-tight capitalize">
                        {bestRound
                          ? `${bestRound.round_type} ${bestRound.score ?? 0}%`
                          : "N/A"}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
