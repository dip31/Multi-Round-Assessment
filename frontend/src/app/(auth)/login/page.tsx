import { AnimatedBG } from "@/components/auth/AnimatedBG";
import { AuthForm } from "@/components/auth/AuthForm";

export default function AuthPage() {
  return (
    <main className="relative flex h-screen w-full overflow-hidden">
      {/* Left Panel */}
      <div className="relative hidden w-1/2 flex-col justify-between bg-primary p-12 lg:flex">
        <AnimatedBG />
        
        <div className="relative z-10 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/20 text-accent">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-heading text-2xl font-bold text-white tracking-tight">PlaceReady</span>
        </div>

        <div className="relative z-10 max-w-lg">
          <h1 className="font-heading text-5xl font-bold leading-[1.15] text-white">
            Prove your potential.<br />
            Land your dream role.
          </h1>
          
          <div className="mt-16 space-y-4">
            <div className="flex animate-[float_6s_ease-in-out_infinite] items-center gap-4 rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur-md">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-500/20 text-teal-400">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </div>
              <p className="text-sm font-medium text-white/90">
                <span className="font-bold text-white">Kumar</span> passed Round 2 — Score: 87/100
              </p>
            </div>
            
            <div className="flex animate-[float_6s_ease-in-out_infinite_1s] items-center gap-4 rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur-md ml-8">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent/20 text-accent-300">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </div>
              <p className="text-sm font-medium text-white/90">
                <span className="font-bold text-white">Priya</span> accepted into TCS — Coding Round cleared
              </p>
            </div>
          </div>
        </div>

        <div className="relative z-10 flex items-center gap-6 text-sm font-medium text-white/60">
          <span>2,000+ Candidates</span>
          <span className="h-1.5 w-1.5 rounded-full bg-white/20" />
          <span>3 Rounds</span>
          <span className="h-1.5 w-1.5 rounded-full bg-white/20" />
          <span>Real-time</span>
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex w-full items-center justify-center bg-surface lg:w-1/2 p-6 overflow-y-auto">
        {/* Mobile Header */}
        <div className="absolute top-8 left-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-accent/10 text-accent">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="font-heading text-xl font-bold text-heading tracking-tight">PlaceReady</span>
        </div>

        <AuthForm />
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
      `}} />
    </main>
  );
}
