import { useEffect, useState } from 'react';

import type { HealthStatus } from '@/types/api';
import HttpS from '@/services/tech/HttpS';

// ============================================================================
// Private
// ============================================================================

const normalize = (raw: string): HealthStatus['status'] =>
  raw === 'ok' || raw === 'degraded' ? raw : 'error';

// ============================================================================
// Public service API
// ============================================================================

const check = async (): Promise<HealthStatus> => {
  const data = await HttpS.get<{ status: string }>('/health');
  return { status: normalize(data.status) };
};

const useHealth = (): HealthStatus | null => {
  const [status, setStatus] = useState<HealthStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const result = await check();
        if (!cancelled) setStatus(result);
      } catch {
        if (!cancelled) setStatus({ status: 'error' });
      }
    };
    void poll();
    const id = setInterval(() => void poll(), 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return status;
};

const HealthS = { check, useHealth };
export default HealthS;
