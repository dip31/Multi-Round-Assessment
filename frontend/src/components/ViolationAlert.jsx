import React, { useEffect, useState } from "react";

export default function ViolationAlert({ violation, onDismiss }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    setVisible(true);
    const t = setTimeout(() => {
      setVisible(false);
      onDismiss && onDismiss();
    }, 5000);
    return () => clearTimeout(t);
  }, [violation]);

  if (!violation || !visible) return null;

  const msg = violation.event_type === "phone_detected" ? "⚠ Mobile phone detected" : "⚠ Multiple people detected";

  return (
    <div className="fixed top-4 right-4 z-50 max-w-xs transform transition-transform" style={{ animation: "slideIn 300ms" }}>
      <div className="bg-red-900/90 border border-red-500 text-red-100 p-4 rounded-md shadow">
        <div className="font-semibold">{msg}</div>
        <div className="text-xs mt-1 text-red-200">{violation?.metadata?.info ?? ""}</div>
      </div>
    </div>
  );
}
