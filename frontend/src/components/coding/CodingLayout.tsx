"use client";

import { ReactNode } from "react";
import { useDeviceType } from "@/hooks/useDeviceType";
import { MobileBlock } from "./MobileBlock";

export function CodingLayout({ children }: { children: ReactNode }) {
  const { isCodingBlocked } = useDeviceType();

  // If the viewport check determined the device is too small, render the blocker screen instead.
  // CRITICAL requirement from SPEC: Mobile Block component renders INSTEAD of the coding IDE.
  if (isCodingBlocked) {
    return <MobileBlock />;
  }

  // Otherwise, return full screen coding environment
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0a0f1e]">
      {children}
    </div>
  );
}
