import { useState, useEffect, useCallback } from "react";
import { MOBILE_BREAKPOINT } from "@/lib/constants";

export function useDeviceType() {
  const [windowWidth, setWindowWidth] = useState<number>(0);

  useEffect(() => {
    // Only run on the client
    setWindowWidth(window.innerWidth);

    const handleResize = () => setWindowWidth(window.innerWidth);

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return {
    isMobile: windowWidth < 768 && windowWidth > 0,
    isTablet: windowWidth >= 768 && windowWidth < MOBILE_BREAKPOINT,
    isDesktop: windowWidth >= MOBILE_BREAKPOINT,
    width: windowWidth,
    // Provide a specific blocked flag to simplify logic
    isCodingBlocked: windowWidth > 0 && windowWidth < MOBILE_BREAKPOINT,
  };
}
