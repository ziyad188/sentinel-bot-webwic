import { useCallback, useEffect, useRef, useState } from 'react';
import { ExternalLink, Image, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SeverityBadge } from '@/components/StatusBadge';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useNavigate } from 'react-router-dom';
import { useProjectSelection } from '@/lib/project';

type IssueMedia = {
  id: string;
  storage_path?: string | null;
  label?: string | null;
  created_at?: string | null;
  url: string;
};

type LatestIssueResponse = {
  id: string;
  project_id: string;
  title?: string | null;
  description?: string | null;
  severity?: string | null;
  slack_url?: string | null;
  slack_user_id?: string | null;
  owner_name?: string | null;
  device_name?: string | null;
  network_name?: string | null;
  created_at?: string | null;
  media: IssueMedia[];
};

export function AlertsPanel() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelection();
  const [latestIssue, setLatestIssue] = useState<LatestIssueResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const isFetchingRef = useRef(false);

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
    async (url: string) => {
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
          headers: {
            Authorization: buildAuthHeader(sessionToken.tokenType, sessionToken.accessToken),
            Accept: 'application/json',
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

  const lastProjectRef = useRef<string | null>(null);

  const fetchLatestIssue = useCallback(async (projectId: string) => {
    if (!projectId) {
      setLatestIssue(null);
      setErrorMessage(null);
      return;
    }

    if (isFetchingRef.current) {
      return;
    }

    try {
      isFetchingRef.current = true;
      setIsLoading(true);
      setErrorMessage(null);

      const params = new URLSearchParams({ project_id: projectId });
      const response = await requestWithSession(`/issues/last/issuedata?${params.toString()}`);
      if (!response) {
        setErrorMessage('Session expired.');
        return;
      }

      if (!response.ok) {
        setErrorMessage('Unable to load latest issue.');
        toast({
          variant: 'destructive',
          title: 'Latest issue failed',
          description: 'We could not load the latest issue. Try again.',
        });
        return;
      }

      const data = (await response.json()) as LatestIssueResponse;
      setLatestIssue(data);
    } catch (error) {
      setErrorMessage('Unable to load latest issue.');
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
      setLatestIssue(null);
      setErrorMessage(null);
      lastProjectRef.current = null;
      return;
    }

    if (lastProjectRef.current === selectedProjectId) {
      return;
    }

    lastProjectRef.current = selectedProjectId;
    void fetchLatestIssue(selectedProjectId);
  }, [fetchLatestIssue, selectedProjectId]);

  const evidenceItem = latestIssue?.media?.[0];

  const handleOpenIssue = () => {
    if (latestIssue?.slack_url) {
      window.open(latestIssue.slack_url, '_blank', 'noopener,noreferrer');
      return;
    }
    navigate('/issues');
  };

  const handleOpenEvidence = () => {
    if (evidenceItem?.url) {
      window.open(evidenceItem.url, '_blank', 'noopener,noreferrer');
      return;
    }
  };

  return (
    <div className="space-y-4">
      {/* Latest Issue */}
      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="border-b border-border px-5 py-4">
          <h3 className="text-sm font-semibold text-card-foreground">Latest Issue Detected</h3>
        </div>
        <div className="p-5 space-y-4">
          {!selectedProjectId && (
            <p className="text-sm text-muted-foreground">
              Select a project to view the latest issue.
            </p>
          )}
          {selectedProjectId && !latestIssue && !isLoading && (
            <p className="text-sm text-muted-foreground">
              {errorMessage ?? 'No issues detected yet.'}
            </p>
          )}
          {selectedProjectId && latestIssue && (
            <>
              <div className="flex items-center gap-2 flex-wrap">
                {latestIssue.severity ? (
                  <SeverityBadge severity={latestIssue.severity as 'P0' | 'P1' | 'P2' | 'P3'} />
                ) : null}
                {latestIssue.created_at && (
                  <span className="text-xs text-muted-foreground">{formatDate(latestIssue.created_at)}</span>
                )}
              </div>
              <p className="text-sm font-semibold text-card-foreground">{latestIssue.title ?? 'Latest issue'}</p>
              <p className="text-sm text-card-foreground leading-relaxed">
                {latestIssue.description ? `${latestIssue.description.slice(0, 150)}...` : '—'}
              </p>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={handleOpenIssue}>
                  <ExternalLink className="h-3 w-3" /> Open Issue
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 text-xs"
                  disabled={!evidenceItem}
                  onClick={handleOpenEvidence}
                >
                  <Image className="h-3 w-3" /> View Evidence
                </Button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Slack Preview */}
      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="border-b border-border px-5 py-4">
          <h3 className="text-sm font-semibold text-card-foreground">Slack Alert Preview</h3>
        </div>
        <div className="p-5">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary">
              <Bot className="h-5 w-5 text-primary-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-bold text-card-foreground">SentinelBot</span>
                <span className="text-[10px] text-muted-foreground">
                  {latestIssue?.created_at ? formatTime(latestIssue.created_at) : '—'}
                </span>
              </div>
              <p className="text-sm font-semibold text-card-foreground mb-2">
                {latestIssue?.title ?? 'Signup Flow Issue Detected'}
              </p>
              <div className="border-l-[3px] border-severity-p0 rounded-r bg-muted/60 p-3 space-y-1.5 text-xs">
                <SlackField label="Environment" value="Staging" />
                <SlackField label="Device" value={latestIssue?.device_name ?? '—'} />
                <SlackField label="Network" value={latestIssue?.network_name ?? '—'} />
                <SlackField label="Severity" value={latestIssue?.severity ?? '—'} />
                <SlackField label="Assigned user" value={latestIssue?.owner_name ?? '—'} />
              </div>
              {/* Evidence thumbnails */}
              <div className="flex gap-2 mt-3">
                <div className="flex items-center gap-1.5 rounded-md border border-border bg-muted/50 px-2.5 py-1.5">
                  <Image className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] text-muted-foreground font-medium">
                    {evidenceItem?.label ?? 'screenshot.png'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SlackField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-muted-foreground">{label}: </span>
      <span className="font-medium text-card-foreground">{value}</span>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return date.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatTime(value?: string | null) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
}
