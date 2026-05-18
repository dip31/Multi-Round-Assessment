"use client";

import { motion } from "framer-motion";

export function AnimatedBG() {
  return (
    <div className="absolute inset-0 overflow-hidden bg-primary w-full h-full z-0">
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-accent/20 blur-[120px] mix-blend-screen" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] rounded-full bg-teal-500/10 blur-[150px] mix-blend-screen" />
      <div className="absolute top-[40%] left-[60%] w-[40%] h-[40%] rounded-full bg-indigo-500/10 blur-[100px] mix-blend-screen" />
      
      {/* CSS-based animated mesh (no JS required for the infinite mesh movement) */}
      <div 
        className="absolute inset-0 opacity-[0.03]" 
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          animation: "move-bg 60s linear infinite",
        }}
      />
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes move-bg {
          0% { background-position: 0 0; }
          100% { background-position: 1000px 1000px; }
        }
      `}} />
    </div>
  );
}
