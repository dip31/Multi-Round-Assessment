import { cn } from "@/lib/utils";
import { Check, CheckCircle2 } from "lucide-react";

export function ProgressStepper() {
  // Hardcoded for mock phase based on spec
  const steps = [
    { number: 1, title: "Aptitude", status: "completed" },
    { number: 2, title: "Coding", status: "active" },
    { number: 3, title: "Interview", status: "locked" },
  ];

  return (
    <div className="flex items-center gap-0">
      {steps.map((step, idx) => (
        <div key={idx} className="flex items-center">
          
          {/* Step Bubble */}
          <div className="flex flex-col items-center gap-1.5 min-w-[64px] relative z-10">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full border-2 bg-primary transition-all duration-300",
                step.status === "completed" && "border-teal-500 text-teal-500",
                step.status === "active" && "border-accent bg-accent text-white",
                step.status === "locked" && "border-gray-500 text-gray-500 opacity-50"
              )}
            >
              {step.status === "completed" ? (
                <CheckCircle2 className="h-4 w-4" strokeWidth={3} />
              ) : (
                <span className="text-sm font-semibold">{step.number}</span>
              )}
            </div>
            
            <span
              className={cn(
                "hidden sm:block absolute -bottom-5 text-xs font-medium uppercase tracking-wider",
                step.status === "completed" ? "text-teal-400" :
                step.status === "active" ? "text-white" : "text-gray-500"
              )}
            >
              {step.title}
            </span>
          </div>

          {/* Connector Line */}
          {idx < steps.length - 1 && (
            <div className="relative w-8 sm:w-16 h-px bg-gray-600/50 mx-1">
              {step.status === "completed" && (
                <div className="absolute inset-0 bg-teal-500 w-full animate-[growWidth_0.5s_ease-out_forwards]" />
              )}
            </div>
          )}
        </div>
      ))}

      <style dangerouslySetInnerHTML={{__html: `
        @keyframes growWidth {
          from { width: 0; }
          to { width: 100%; }
        }
      `}} />
    </div>
  );
}
