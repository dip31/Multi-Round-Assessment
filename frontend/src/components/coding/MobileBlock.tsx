import { Monitor, ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/shared/Toast";

export function MobileBlock() {
  const router = useRouter();
  const { toast } = useToast();

  const handleSendLink = () => {
    toast({
      title: "Link Sent",
      description: "We've sent a link to your registered email address.",
    });
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white px-6 py-12 text-center">
      <div className="mb-8 flex items-center justify-center">
        <div className="flex h-10 w-10 items-center justify-center rounded bg-accent/20 text-accent">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>
      
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-2xl bg-accent/10 text-accent">
        <Monitor className="h-10 w-10" />
      </div>
      
      <h2 className="mb-3 max-w-[320px] font-heading text-2xl font-bold text-heading">
        Coding Round requires a desktop browser
      </h2>
      
      <p className="mb-10 max-w-[340px] text-[15px] leading-relaxed text-muted-foreground">
        For the best experience, please open this page on a laptop or desktop with a minimum screen width of 1024px.
      </p>

      <div className="flex w-full max-w-[320px] flex-col gap-4 relative z-50">
        <button
          onClick={handleSendLink}
          className="flex h-12 w-full items-center justify-center rounded-lg border-2 border-accent text-accent font-semibold transition-colors hover:bg-accent/5 focus:ring-2 focus:ring-accent/40"
        >
          Send link to email
        </button>
        
        <button
          onClick={() => router.push("/dashboard")}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-lg font-medium text-muted-foreground transition-colors hover:text-heading"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </button>
      </div>
    </div>
  );
}
