import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../services/api';

/**
 * Loads the authenticated role dashboard from the API.
 *
 * The API returns explicit empty collections/null values for new accounts,
 * which prevents demo identity, scores, and assessment history from leaking
 * into a real user's dashboard.
 */
export function useDashboardData(role) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/dashboard/${role}`);
      if (currentRequest === requestId.current) setData(response.data);
    } catch (requestError) {
      if (currentRequest === requestId.current) {
        setData(null);
        setError(requestError);
      }
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, [role]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, refetch: load };
}

export default useDashboardData;
