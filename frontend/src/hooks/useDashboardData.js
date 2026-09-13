/**
 * useDashboardData — single data entry point for every role dashboard.
 *
 * Today it resolves a per-role mock module after a short simulated latency so
 * the loading / error / empty states are all reachable in the UI. To move to a
 * real backend, replace the body of `load()` with:
 *
 *     const res = await api.get(`/dashboard/${role}`);
 *     return res.data;
 *
 * ...and delete the MOCK_REGISTRY. Nothing else in the UI needs to change,
 * because the mock modules already use the backend's field vocabulary.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import studentDashboardData from '../data/studentDashboardData';

/** Simulated network latency, ms. Keeps the skeleton visible long enough to see. */
const MOCK_LATENCY_MS = 550;

/**
 * Role -> mock module. Entries are added as each role's data file lands.
 * An unregistered role surfaces as an error, which renders <ErrorState />.
 */
const MOCK_REGISTRY = {
  student: studentDashboardData,
};

export function useDashboardData(role) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Guards against setting state after unmount, and against a stale
  // in-flight load overwriting a newer one when `role` changes quickly.
  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(() => {
    const requestId = ++requestIdRef.current;

    setLoading(true);
    setError(null);

    const timer = setTimeout(() => {
      // Ignore if unmounted or superseded by a newer request.
      if (!mountedRef.current || requestId !== requestIdRef.current) return;

      const payload = MOCK_REGISTRY[role];

      if (!payload) {
        setData(null);
        setError(
          new Error(
            `No dashboard data available for role "${role}". ` +
              'Register a mock module in useDashboardData, or point this hook at the API.'
          )
        );
        setLoading(false);
        return;
      }

      setData(payload);
      setError(null);
      setLoading(false);
    }, MOCK_LATENCY_MS);

    return () => clearTimeout(timer);
  }, [role]);

  useEffect(() => {
    const cancel = load();
    return cancel;
  }, [load]);

  const refetch = useCallback(() => {
    load();
  }, [load]);

  return { data, loading, error, refetch };
}

export default useDashboardData;
