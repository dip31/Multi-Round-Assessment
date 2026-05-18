import { useToast as useHookToast } from "@/hooks/use-toast";

// Re-exporting from shadcn to keep our shared imports clean
export { Toaster } from "@/components/ui/toaster";

export function useToast() {
  const { toast } = useHookToast();
  
  return {
    toast,
    success: (title: string, description?: string) => 
      toast({ title, description, variant: "default", className: "border-teal-500 bg-teal-50 text-teal-900" }),
    error: (title: string, description?: string) => 
      toast({ title, description, variant: "destructive" }),
    info: (title: string, description?: string) => 
      toast({ title, description, className: "bg-surface text-foreground" }),
  };
}
