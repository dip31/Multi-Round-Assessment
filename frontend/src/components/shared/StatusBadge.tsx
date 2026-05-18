import { AlertCircle, CheckCircle2, Clock, Info, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  variant: "success" | "warning" | "error" | "info" | "locked";
  label: string;
  className?: string;
}

const variants = {
  success: {
    bg: "bg-teal-100 dark:bg-teal-900/30",
    text: "text-teal-700 dark:text-teal-400",
    icon: CheckCircle2,
  },
  warning: {
    bg: "bg-amber-100 dark:bg-amber-900/30",
    text: "text-amber-700 dark:text-amber-400",
    icon: Clock,
  },
  error: {
    bg: "bg-red-100 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-400",
    icon: AlertCircle,
  },
  info: {
    bg: "bg-blue-100 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-400",
    icon: Info,
  },
  locked: {
    bg: "bg-gray-100 dark:bg-gray-800",
    text: "text-gray-500 dark:text-gray-400",
    icon: Lock,
  },
};

export function StatusBadge({ variant, label, className }: StatusBadgeProps) {
  const config = variants[variant];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        config.bg,
        config.text,
        className
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}
