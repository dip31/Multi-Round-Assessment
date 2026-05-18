"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, User } from "lucide-react";

export function Navbar() {
  const pathname = usePathname();

  // Determine active steps visually
  const isAptitudeActive = pathname.includes("aptitude");
  const isCodingActive = pathname.includes("coding");
  const isInterviewActive = pathname.includes("interview");

  const isAptitudeDone = isCodingActive || isInterviewActive || pathname === "/results";
  const isCodingDone = isInterviewActive || pathname === "/results";

  return (
    <nav className="sticky top-0 z-50 flex h-16 w-full items-center justify-between bg-primary px-6 text-white shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-accent/20 text-accent">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <Link href="/dashboard" className="font-heading text-lg font-bold tracking-tight">
          PlaceReady
        </Link>
      </div>

      <div className="hidden items-center gap-4 md:flex">
        <StepIndicator 
          label="Aptitude" 
          number={1} 
          status={isAptitudeDone ? "done" : isAptitudeActive ? "active" : "pending"} 
        />
        <div className={`h-px w-8 ${isAptitudeDone ? "bg-teal-500" : "bg-white/20"}`} />
        <StepIndicator 
          label="Coding" 
          number={2} 
          status={isCodingDone ? "done" : isCodingActive ? "active" : "pending"} 
        />
        <div className={`h-px w-8 ${isCodingDone ? "bg-teal-500" : "bg-white/20"}`} />
        <StepIndicator 
          label="Interview" 
          number={3} 
          status={isInterviewActive ? "active" : "locked"} 
        />
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden flex-col items-end sm:flex">
          <span className="text-sm font-medium">Kumar Raj</span>
          <span className="text-xs text-muted-foreground">kumar@example.com</span>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10">
          <User className="h-5 w-5" />
        </div>
        <button className="ml-2 text-white/70 hover:text-white transition-colors" title="Log out">
          <LogOut className="h-5 w-5" />
        </button>
      </div>
    </nav>
  );
}

function StepIndicator({ 
  label, 
  number, 
  status 
}: { 
  label: string; 
  number: number; 
  status: "done" | "active" | "pending" | "locked" 
}) {
  let indicatorClasses = "";
  
  if (status === "done") {
    indicatorClasses = "bg-teal-500 text-primary border-teal-500";
  } else if (status === "active") {
    indicatorClasses = "bg-accent border-accent text-white";
  } else if (status === "locked") {
    indicatorClasses = "border-white/20 text-white/40";
  } else {
    indicatorClasses = "border-white/50 text-white/70";
  }

  return (
    <div className="flex items-center gap-2">
      <div className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs font-semibold ${indicatorClasses}`}>
        {status === "done" ? (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 6L9 17L4 12" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        ) : (
          number
        )}
      </div>
      <span className={`text-sm font-medium ${status === "locked" ? "text-white/40" : status === "active" ? "text-white" : "text-white/80"}`}>
        {label}
      </span>
    </div>
  );
}
