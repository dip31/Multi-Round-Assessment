import { useState, useEffect } from "react";

const MAX_SIZE = 50 * 1024; // 50KB

export function useCodePersist(problemId: number, language: string) {
  const key = `code_${problemId}_${language}`;
  const [code, setCode] = useState("");

  // Reload saved code when problem or language changes
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem(key);
      setCode(saved || "");
    } catch {
      setCode("");
    }
  }, [key]);

  // Debounced save
  useEffect(() => {
    if (typeof window === "undefined") return;
    
    const timeout = setTimeout(() => {
      try {
        if (new Blob([code]).size < MAX_SIZE && code.trim() !== '') {
          window.localStorage.setItem(key, code);
        }
      } catch (e) {
        console.error("Local storage error:", e);
      }
    }, 500);

    return () => clearTimeout(timeout);
  }, [code, key]);

  return { code, setCode };
}
