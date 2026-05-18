import { cn } from "@/lib/utils";
import { VERDICT } from "@/lib/constants";
import { CheckCircle, XCircle, AlertTriangle, Clock } from "lucide-react";

interface VerdictBannerProps {
  verdict: string;
  message: string;
  className?: string;
}

export function VerdictBanner({ verdict, message, className }: VerdictBannerProps) {
  let config = {
    bg: "bg-gray-100",
    text: "text-gray-800",
    border: "border-gray-200",
    icon: AlertTriangle,
  };

  switch (verdict) {
    case VERDICT.ACCEPTED:
      config = {
        bg: "bg-teal-50 dark:bg-teal-900/20",
        text: "text-teal-800 dark:text-teal-300",
        border: "border-teal-200 dark:border-teal-800",
        icon: CheckCircle,
      };
      break;
    case VERDICT.PARTIAL:
    case VERDICT.TIME_LIMIT_EXCEEDED:
      config = {
        bg: "bg-amber-50 dark:bg-amber-900/20",
        text: "text-amber-800 dark:text-amber-300",
        border: "border-amber-200 dark:border-amber-800",
        icon: Clock,
      };
      break;
    case VERDICT.WRONG_ANSWER:
    case VERDICT.RUNTIME_ERROR:
      config = {
        bg: "bg-red-50 dark:bg-red-900/20",
        text: "text-red-800 dark:text-red-300",
        border: "border-red-200 dark:border-red-800",
        icon: XCircle,
      };
      break;
    case VERDICT.COMPILATION_ERROR:
      config = {
        bg: "bg-gray-100 dark:bg-gray-800",
        text: "text-gray-800 dark:text-gray-300",
        border: "border-gray-200 dark:border-gray-700",
        icon: AlertTriangle,
      };
      break;
  }

  const Icon = config.icon;

  return (
    <div
      className={cn(
        "flex w-full items-center gap-3 rounded-lg border p-4",
        config.bg,
        config.border,
        config.text,
        className
      )}
      role="alert"
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
}
