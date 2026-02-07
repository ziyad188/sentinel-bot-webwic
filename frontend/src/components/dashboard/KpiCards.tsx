import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, Clock, Zap } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useNavigate } from 'react-router-dom';
import { useProjectSelection } from '@/lib/project';

type SummaryResponse = {
  project_id: string;
  date: string;
  runs_count: number;
  issues_count: number;
  p0_count: number;
  p1_count: number;
  avg_issue_time_ms: number;
};

export function KpiCards() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelection();
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const isFetchingRef = useRef(false);
  const lastRequestRef = useRef<string | null>(null);

  const today = useMemo(() => formatLocalDate(new Date()), []);

  const handleSessionExpired = useCallback(() => {
    clearStoredAuth();
    toast({
      variant: 'destructive',
      title: 'Session expired',
      description: 'Please sign in again.',
    });
    navigate('/login', { replace: true });
  }, [navigate, toast]);

  const requestWithSession = useCallback(
    async (url: string, init?: RequestInit) => {
      const record = getStoredSessionRecord();
      if (!record?.session?.accessToken) {
        handleSessionExpired();
        return null;
      }

      let activeSession = record.session;
      if (isSessionExpired(activeSession)) {
        const refreshed = await refreshSession(activeSession, record.remember);
        if (!refreshed) {
          handleSessionExpired();
          return null;
        }
        activeSession = refreshed;
      }

      const buildAuthHeader = (tokenType: string, accessToken: string) => {
        const normalized = tokenType
          ? `${tokenType[0].toUpperCase()}${tokenType.slice(1)}`
          : 'Bearer';
        return `${normalized} ${accessToken}`;
      };

      const executeRequest = (sessionToken: { tokenType: string; accessToken: string }) =>
        fetch(url, {
          ...init,
          headers: {
            Authorization: buildAuthHeader(sessionToken.tokenType, sessionToken.accessToken),
            Accept: 'application/json',
            ...(init?.headers ?? {}),
          },
        });

      let response = await executeRequest(activeSession);
      if (response.status === 401) {
        const refreshed = await refreshSession(activeSession, record.remember);
        if (!refreshed) {
          handleSessionExpired();
          return null;
        }
        activeSession = refreshed;
        response = await executeRequest(activeSession);
      }

      if (response.status === 401) {
        handleSessionExpired();
        return null;
      }

      return response;
    },
    [handleSessionExpired],
  );

  const fetchSummary = useCallback(async (projectId: string, date: string) => {
    if (!projectId) {
      setSummary(null);
      return;
    }

    if (isFetchingRef.current) {
      return;
    }

    const requestKey = `${projectId}:${date}`;
    if (lastRequestRef.current === requestKey) {
      return;
    }

    try {
      isFetchingRef.current = true;
      setIsLoading(true);
      lastRequestRef.current = requestKey;

      const response = await requestWithSession('/widgets/summary', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: projectId,
          date,
        }),
      });

      if (!response) {
        return;
      }

      if (!response.ok) {
        toast({
          variant: 'destructive',
          title: 'Summary failed',
          description: 'We could not load the summary. Try again.',
        });
        return;
      }

      const data = (await response.json()) as SummaryResponse;
      setSummary(data);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    } finally {
      isFetchingRef.current = false;
      setIsLoading(false);
    }
  }, [requestWithSession, toast]);

  useEffect(() => {
    if (!selectedProjectId) {
      setSummary(null);
      lastRequestRef.current = null;
      return;
    }
    void fetchSummary(selectedProjectId, today);
  }, [fetchSummary, selectedProjectId, today]);

  const runs = summary?.runs_count ?? null;
  const issues = summary?.issues_count ?? null;
  const avgMs = summary?.avg_issue_time_ms ?? null;
  const critical = summary ? summary.p0_count + summary.p1_count : null;

  const cards = [
    { label: 'Runs today', value: runs, icon: Activity, format: (v: number) => v.toString() },
    { label: 'Issues detected', value: issues, icon: AlertTriangle, format: (v: number) => v.toString() },
    { label: 'Avg time to detect', value: avgMs, icon: Clock, format: (v: number) => `${Math.round(v / 100) / 10}s` },
    { label: 'Critical blockers (P0/P1)', value: critical, icon: Zap, format: (v: number) => v.toString() },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {cards.map(({ label, value, icon: Icon, format }) => (
        <div key={label} className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
            <Icon className="h-4 w-4 text-muted-foreground" />
          </div>
          <p className="text-3xl font-bold tracking-tight text-card-foreground">
            {value === null || typeof value === 'undefined' ? (isLoading ? '—' : '—') : format(value)}
          </p>
        </div>
      ))}
    </div>
  );
}

function formatLocalDate(date: Date) {
  return new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}
