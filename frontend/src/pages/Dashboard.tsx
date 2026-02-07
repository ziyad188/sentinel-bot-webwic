import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { KpiCards } from '@/components/dashboard/KpiCards';
import { LiveRunPanel } from '@/components/dashboard/LiveRunPanel';
import { AlertsPanel } from '@/components/dashboard/AlertsPanel';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useProjectSelection } from '@/lib/project';
import { useRunConfig } from '@/lib/run-config';

const Dashboard = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelection();
  const { runConfig } = useRunConfig();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isDemoMode = String(import.meta.env.VITE_DEMO_MODE ?? "").toLowerCase() === "true";

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

  const handleRunNow = async () => {
    if (!isDemoMode) {
      toast({
        title: 'Demo mode disabled',
        description:
          'Run workflow is disabled in this environment to avoid cloud billing. See the demo video instead.',
      });
      return;
    }

    if (!selectedProjectId) {
      toast({
        variant: 'destructive',
        title: 'Select a project',
        description: 'Choose a project before starting a run.',
      });
      return;
    }

    if (!runConfig.deviceId || !runConfig.networkId) {
      toast({
        variant: 'destructive',
        title: 'Select device and network',
        description: 'Choose a device and network before starting a run.',
      });
      return;
    }

    if (isSubmitting) {
      return;
    }

    const payload: {
      project_id: string;
      status: string;
      result?: string | null;
      locale?: string | null;
      persona?: string | null;
      device_id?: string;
      network_id?: string;
      started_at?: string | null;
      input_data?: Record<string, unknown> | null;
    } = {
      project_id: selectedProjectId,
      status: 'queued',
      locale: 'en-US',
      persona: runConfig.persona || 'first_time_user',
    };

    payload.device_id = runConfig.deviceId;
    payload.network_id = runConfig.networkId;
    if (runConfig.inputJson?.trim()) {
      try {
        payload.input_data = JSON.parse(runConfig.inputJson);
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Invalid JSON',
          description: 'Input JSON must be valid before running.',
        });
        return;
      }
    }

    try {
      setIsSubmitting(true);
      const response = await requestWithSession('/runs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response) {
        return;
      }

      if (!response.ok) {
        toast({
          variant: 'destructive',
          title: 'Run failed',
          description: 'Unable to start the run. Try again.',
        });
        return;
      }

      const data = (await response.json()) as { id: string };
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('sentinelbot:last-run-id', data.id);
      }

      toast({
        title: 'Run queued',
        description: 'Your run is now in the queue.',
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Autonomous Signup Monitoring</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Vision-driven agent runs through signup flows across desktop, tablet, and mobile to detect friction and escalate issues with evidence.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button className="gap-1.5" onClick={handleRunNow} disabled={isSubmitting}>
            <Play className="h-4 w-4" /> Run now
          </Button>
        </div>
      </div>

      {/* KPIs */}
      <KpiCards />

      {/* Two column layout */}
      <div className="grid grid-cols-5 gap-6">
        <div className="col-span-3">
          <LiveRunPanel />
        </div>
        <div className="col-span-2">
          <AlertsPanel />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
