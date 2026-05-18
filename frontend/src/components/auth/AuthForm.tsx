"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import API from "@/lib/api";

export function AuthForm() {
  const router = useRouter();
  const { setToken, setUser } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const [formData, setFormData] = useState({ name: "", email: "", password: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (mode === "register" && !formData.name.trim()) newErrors.name = "Name is required";
    if (!formData.email.trim()) newErrors.email = "Email is required";
    else if (!/\S+@\S+\.\S+/.test(formData.email)) newErrors.email = "Invalid email format";
    if (!formData.password) newErrors.password = "Password is required";
    else if (formData.password.length < 8) newErrors.password = "Must be at least 8 characters";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /** Decode JWT payload to extract user info */
  const decodeJwtPayload = (token: string): { sub: string } | null => {
    try {
      const base64 = token.split(".")[1];
      const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
      return JSON.parse(json);
    } catch {
      return null;
    }
  };

  /** Call POST /auth/login with JSON body */
  const loginUser = async (email: string, password: string) => {
    const res = await API.post("/auth/login", { email, password });
    const { access_token } = res.data;

    setToken(access_token);

    // Decode JWT for user_id, then store basic user info
    const payload = decodeJwtPayload(access_token);
    if (payload?.sub) {
      setUser({ id: Number(payload.sub), name: formData.name || email.split("@")[0], email });
    }

    router.push("/dashboard");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    setErrors({});

    try {
      if (mode === "register") {
        // Step 1: Register
        try {
          await API.post("/auth/register", {
            name: formData.name,
            email: formData.email,
            password: formData.password,
          });
        } catch (regErr: any) {
          const status = regErr.response?.status;
          const detail = regErr.response?.data?.detail;

          if (status === 409) {
            setErrors({ email: "This email is already registered" });
            setLoading(false);
            return;
          }
          if (status === 422 && Array.isArray(detail)) {
            const fieldErrors: Record<string, string> = {};
            for (const err of detail) {
              const field = err.loc?.[err.loc.length - 1];
              if (field) fieldErrors[field] = err.msg;
            }
            setErrors(fieldErrors);
            setLoading(false);
            return;
          }
          throw regErr; // re-throw unexpected errors
        }

        // Step 2: Auto-login after successful registration
        await loginUser(formData.email, formData.password);
      } else {
        // Login flow
        await loginUser(formData.email, formData.password);
      }
    } catch (err: any) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;

      if (status === 401) {
        setErrors({ password: "Invalid email or password" });
      } else if (status === 422 && Array.isArray(detail)) {
        const fieldErrors: Record<string, string> = {};
        for (const d of detail) {
          const field = d.loc?.[d.loc.length - 1];
          if (field) fieldErrors[field] = d.msg;
        }
        setErrors(fieldErrors);
      } else if (!err.response) {
        setErrors({ password: "No internet connection. Please try again." });
      } else {
        setErrors({ password: "Something went wrong. Please try again." });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-[440px] px-8 py-10 bg-white rounded-2xl shadow-xl shadow-accent/5">
      {/* Tab Switcher */}
      <div className="flex w-full mb-8 bg-gray-100 rounded-full p-1 border border-gray-200">
        <button
          type="button"
          onClick={() => { setMode("login"); setErrors({}); }}
          className={cn(
            "flex-1 py-2 text-sm font-semibold rounded-full transition-all text-center",
            mode === "login" ? "bg-accent text-white shadow-md" : "text-gray-500 hover:text-gray-900"
          )}
        >
          LOGIN
        </button>
        <button
          type="button"
          onClick={() => { setMode("register"); setErrors({}); }}
          className={cn(
            "flex-1 py-2 text-sm font-semibold rounded-full transition-all text-center",
            mode === "register" ? "bg-accent text-white shadow-md" : "text-gray-500 hover:text-gray-900"
          )}
        >
          REGISTER
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">

        {mode === "register" && (
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-heading">Full Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              disabled={loading}
              className={cn(
                "w-full h-12 px-4 rounded-lg border bg-surface outline-none focus:ring-2 focus:ring-accent/50 transition-all disabled:opacity-60",
                errors.name ? "border-red-500 focus:border-red-500 bg-red-50" : "border-gray-200 focus:border-accent"
              )}
              placeholder="Kumar Raj"
            />
            {errors.name && <p className="text-xs text-red-500 font-medium">{errors.name}</p>}
          </div>
        )}

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-heading">Email Address</label>
          <input
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            disabled={loading}
            className={cn(
              "w-full h-12 px-4 rounded-lg border bg-surface outline-none focus:ring-2 focus:ring-accent/50 transition-all disabled:opacity-60",
              errors.email ? "border-red-500 focus:border-red-500 bg-red-50" : "border-gray-200 focus:border-accent"
            )}
            placeholder="kumar@example.com"
          />
          {errors.email && <p className="text-xs text-red-500 font-medium">{errors.email}</p>}
        </div>

        <div className="space-y-1.5 relative">
          <label className="text-sm font-medium text-heading">Password</label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              disabled={loading}
              className={cn(
                "w-full h-12 pl-4 pr-12 rounded-lg border bg-surface outline-none focus:ring-2 focus:ring-accent/50 transition-all disabled:opacity-60",
                errors.password ? "border-red-500 focus:border-red-500 bg-red-50" : "border-gray-200 focus:border-accent"
              )}
              placeholder="••••••••"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 focus:outline-none"
            >
              {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>
          {errors.password && <p className="text-xs text-red-500 font-medium">{errors.password}</p>}
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 rounded-lg bg-accent text-white font-heading font-bold flex items-center justify-center gap-2 hover:bg-accent/90 focus:ring-4 focus:ring-accent/20 transition-all active:scale-[0.98] disabled:opacity-70 disabled:active:scale-100"
          >
            {loading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>CONTINUE</span>
            )}
          </button>
        </div>

        <div className="pt-4 text-center">
          <p className="text-xs text-muted-foreground max-w-[80%] mx-auto leading-relaxed">
            By continuing, you agree to PlaceReady&apos;s Terms of Service and Privacy Policy.
          </p>
        </div>
      </form>
    </div>
  );
}
