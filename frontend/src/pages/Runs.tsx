import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RunStatusBadge, SeverityBadge } from '@/components/StatusBadge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useNavigate } from 'react-router-dom';
import { useProjectSelection } from '@/lib/project';
import { cn } from '@/lib/utils';

type IssueSummary = {
  id: string;
  title?: string | null;
  severity?: string | null;
  status?: string | null;
};

type RunListItem = {
  id: string;
  display_id: string;
  started_at?: string | null;
  duration_ms?: number | null;
  device_id?: string | null;
  device_name?: string | null;
  network_id?: string | null;
  network_name?: string | null;
  locale?: string | null;
  status: string;
  result?: string | null;
  issues?: IssueSummary[];
};

type RunListResponse = {
  items: RunListItem[];
  total: number;
  page: number;
  page_size: number;
};

type RunIssue = {
  idx: number;
  id: string;
  project_id: string;
  title?: string | null;
  description?: string | null;
  severity?: string | null;
  category?: string | null;
  owner_team?: string | null;
  status?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
  run_id: string;
  slack_url?: string | null;
};

type RunMedia = {
  id: string;
  run_id: string;
  issue_id?: string | null;
  type: string;
  storage_path?: string | null;
  label?: string | null;
  created_at?: string | null;
  url: string;
};

type RunIssueResponse = {
  project_id: string;
  run_id: string;
  issues: RunIssue[];
  media: RunMedia[];
};

const Runs = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelection();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [selectedRun, setSelectedRun] = useState<RunListItem | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const isFetchingRef = useRef(false);
  const [detailsByRunId, setDetailsByRunId] = useState<Record<string, RunIssueResponse>>({});
  const [detailsLoadingId, setDetailsLoadingId] = useState<string | null>(null);
  const [activeMedia, setActiveMedia] = useState<RunMedia | null>(null);

  const effectivePageSize = pageSize || 20;
  const totalPages = Math.max(1, Math.ceil(total / effectivePageSize));

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

  const fetchRuns = useCallback(
    async (requestedPage: number, replace = false) => {
      if (!selectedProjectId) {
        setRuns([]);
        setTotal(0);
        return;
      }

      if (isFetchingRef.current) {
        return;
      }

      try {
        isFetchingRef.current = true;
        setIsLoading(true);
        setErrorMessage(null);

        const params = new URLSearchParams({
          project_id: selectedProjectId,
          page: String(requestedPage),
          page_size: String(pageSize),
        });

        if (statusFilter !== 'all') {
          params.set('status', statusFilter.toLowerCase());
        }

        if (severityFilter !== 'all') {
          params.set('severity', severityFilter.toUpperCase());
        }

        const response = await requestWithSession(`/runs?${params.toString()}`);
        if (!response) {
          setErrorMessage('Session expired.');
          return;
        }

        if (!response.ok) {
          setErrorMessage('Unable to load runs.');
          toast({
            variant: 'destructive',
            title: 'Runs failed',
            description: 'We could not load runs. Try again.',
          });
          return;
        }

        const data = (await response.json()) as RunListResponse;
        const items = data.items ?? [];
        setRuns((prev) => (replace ? items : [...prev, ...items]));
        setTotal(data.total ?? items.length);
        setPage(data.page ?? requestedPage);
        setPageSize(data.page_size ?? pageSize);
      } catch (error) {
        setErrorMessage('Unable to load runs.');
        toast({
          variant: 'destructive',
          title: 'Network error',
          description: 'We could not reach the server. Try again.',
        });
      } finally {
        isFetchingRef.current = false;
        setIsLoading(false);
      }
    },
    [pageSize, requestWithSession, selectedProjectId, severityFilter, statusFilter, toast],
  );

  const fetchRunDetails = useCallback(
    async (runId: string) => {
      if (!selectedProjectId || detailsLoadingId === runId || detailsByRunId[runId]) {
        return;
      }

      try {
        setDetailsLoadingId(runId);
        const params = new URLSearchParams({
          project_id: selectedProjectId,
        });

        const response = await requestWithSession(`/runs/${runId}/issues?${params.toString()}`);
        if (!response) {
          return;
        }

        if (!response.ok) {
          toast({
            variant: 'destructive',
            title: 'Run details failed',
            description: 'Unable to load run details. Try again.',
          });
          return;
        }

        const data = (await response.json()) as RunIssueResponse;
        setDetailsByRunId((prev) => ({ ...prev, [runId]: data }));
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Network error',
          description: 'We could not reach the server. Try again.',
        });
      } finally {
        setDetailsLoadingId((prev) => (prev === runId ? null : prev));
      }
    },
    [detailsByRunId, detailsLoadingId, requestWithSession, selectedProjectId, toast],
  );

  useEffect(() => {
    setPage(1);
    if (selectedProjectId) {
      void fetchRuns(1, true);
    }
  }, [fetchRuns, selectedProjectId, severityFilter, statusFilter]);

  useEffect(() => {
    if (selectedRun) {
      void fetchRunDetails(selectedRun.id);
    }
  }, [fetchRunDetails, selectedRun]);

  const handlePageChange = (nextPage: number) => {
    if (isLoading) {
      return;
    }
    const target = Math.min(Math.max(nextPage, 1), totalPages);
    setPage(target);
    void fetchRuns(target, true);
  };

  const normalizedRuns = useMemo(() => {
    const severityOrder = ['P0', 'P1', 'P2', 'P3'];
    const normalizeSeverity = (value?: string | null) => value?.toUpperCase() ?? null;

    return runs.map((run) => {
      const issues = run.issues ?? [];
      const normalizedSeverities = issues
        .map((issue) => normalizeSeverity(issue.severity))
        .filter((severity): severity is string => !!severity);
      const highestSeverity = normalizedSeverities.sort(
        (a, b) => severityOrder.indexOf(a) - severityOrder.indexOf(b),
      )[0];

      return {
        ...run,
        derivedSeverity: highestSeverity,
        derivedResult:
          normalizeResult(run.result, issues.length),
      };
    });
  }, [runs]);

  return (
    <div className="space-y-6 max-w-[1400px]">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Runs</h1>
        <p className="mt-1 text-sm text-muted-foreground">All agent runs with results and detailed timelines.</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter} disabled={!selectedProjectId}>
          <SelectTrigger className="w-40 h-9 text-xs bg-card"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent className="bg-popover">
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>
        <Select value={severityFilter} onValueChange={setSeverityFilter} disabled={!selectedProjectId}>
          <SelectTrigger className="w-40 h-9 text-xs bg-card"><SelectValue placeholder="Severity" /></SelectTrigger>
          <SelectContent className="bg-popover">
            <SelectItem value="all">Any severity</SelectItem>
            <SelectItem value="P0">P0</SelectItem>
            <SelectItem value="P1">P1</SelectItem>
            <SelectItem value="P2">P2</SelectItem>
            <SelectItem value="P3">P3</SelectItem>
          </SelectContent>
        </Select>
        {!selectedProjectId && (
          <span className="text-xs text-muted-foreground self-center">
            Select a project to view runs.
          </span>
        )}
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Run ID</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Started</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Duration</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Device</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Network</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Locale</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Status</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Result</th>
            </tr>
          </thead>
          <tbody>
            {normalizedRuns.map(run => (
              <tr
                key={run.id}
                className="border-b border-border last:border-0 hover:bg-muted/30 cursor-pointer transition-colors"
                onClick={() => setSelectedRun(run)}
              >
                <td className="px-4 py-3 font-mono text-xs font-medium text-foreground">{run.display_id}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {formatStartedAt(run.started_at)}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {run.duration_ms ? `${Math.round(run.duration_ms / 100) / 10}s` : '—'}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{run.device_name ?? '—'}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{run.network_name ?? '—'}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{normalizeLocale(run.locale)}</td>
                <td className="px-4 py-3">
                  <RunStatusBadge status={toBadgeStatus(run.status)} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className={cn('text-xs font-medium',
                      run.derivedResult === 'Crash' ? 'text-severity-p0' :
                      run.derivedResult === 'Issue found' ? 'text-severity-p0' : 'text-status-success'
                    )}>{run.derivedResult}</span>
                    {run.derivedSeverity && <SeverityBadge severity={run.derivedSeverity as 'P0' | 'P1' | 'P2' | 'P3'} />}
                  </div>
                </td>
              </tr>
            ))}
            {normalizedRuns.length === 0 && !isLoading && (
              <tr>
                <td className="px-4 py-6 text-sm text-muted-foreground" colSpan={8}>
                  {errorMessage ?? (selectedProjectId ? 'No runs found for this project.' : 'Select a project to view runs.')}
                </td>
              </tr>
            )}
            {isLoading && (
              <tr>
                <td className="px-4 py-6 text-sm text-muted-foreground" colSpan={8}>
                  Loading runs...
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            Page {page} of {totalPages} · {total} runs
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(page - 1)}
              disabled={isLoading || page <= 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(page + 1)}
              disabled={isLoading || page >= totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Run Detail Drawer */}
      <Sheet open={!!selectedRun} onOpenChange={() => setSelectedRun(null)}>
        <SheetContent className="w-[480px] sm:max-w-[480px] bg-card overflow-y-auto">
          {selectedRun && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-3">
                  <span className="font-mono">{selectedRun.display_id}</span>
                  <RunStatusBadge status={toBadgeStatus(selectedRun.status)} />
                </SheetTitle>
              </SheetHeader>

              <div className="mt-6 space-y-6">
                {/* Meta */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <MetaField label="Device" value={selectedRun.device_name ?? '—'} />
                  <MetaField label="Network" value={selectedRun.network_name ?? '—'} />
                  <MetaField label="Locale" value={normalizeLocale(selectedRun.locale)} />
                  <MetaField label="Duration" value={selectedRun.duration_ms ? `${Math.round(selectedRun.duration_ms / 100) / 10}s` : '—'} />
                  <MetaField label="Result" value={normalizeResult(selectedRun.result, selectedRun.issues?.length ?? 0) ?? '—'} />
                </div>

                {/* Issues */}
                <div>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Issues</h4>
                  {detailsLoadingId === selectedRun.id && (
                    <div className="text-xs text-muted-foreground">Loading issues...</div>
                  )}
                  {detailsByRunId[selectedRun.id]?.issues?.length ? (
                    <div className="space-y-2">
                      {detailsByRunId[selectedRun.id].issues.map((issue) => (
                        <div key={issue.id} className="rounded-lg border border-border bg-muted/50 px-3 py-2 space-y-1">
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-sm font-medium text-card-foreground">
                              {issue.title ?? 'Untitled issue'}
                            </div>
                            {issue.severity && (
                              <SeverityBadge severity={issue.severity.toUpperCase() as 'P0' | 'P1' | 'P2' | 'P3'} />
                            )}
                          </div>
                          {issue.description && (
                            <div className="text-xs text-muted-foreground">{issue.description}</div>
                          )}
                          <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                            {issue.status && <span>Status: {normalizeIssueStatus(issue.status)}</span>}
                            {issue.category && <span>Category: {issue.category}</span>}
                            {issue.created_at && <span>Created: {formatStartedAt(issue.created_at)}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    !detailsLoadingId && (
                      <div className="text-xs text-muted-foreground">No issues recorded for this run.</div>
                    )
                  )}
                </div>

                {/* Media */}
                <div>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Media</h4>
                  {detailsLoadingId === selectedRun.id && (
                    <div className="text-xs text-muted-foreground">Loading media...</div>
                  )}
                  {detailsByRunId[selectedRun.id]?.media?.length ? (
                    <div className="grid grid-cols-2 gap-3">
                      {detailsByRunId[selectedRun.id].media.map((media) => (
                        <button
                          key={media.id}
                          type="button"
                          className="rounded-lg border border-border bg-muted/50 p-2 text-left transition hover:border-primary/40 hover:bg-muted"
                          onClick={() => setActiveMedia(media)}
                        >
                          <div className="text-[10px] text-muted-foreground mb-2">
                            {media.label ?? media.type}
                          </div>
                          {media.type === 'video' ? (
                            <video className="w-full rounded-md">
                              <source src={media.url} />
                            </video>
                          ) : (
                            <img src={media.url} alt={media.label ?? 'Run media'} className="w-full rounded-md" />
                          )}
                        </button>
                      ))}
                    </div>
                  ) : (
                    !detailsLoadingId && (
                      <div className="text-xs text-muted-foreground">No media available for this run.</div>
                    )
                  )}
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={!!activeMedia} onOpenChange={(open) => !open && setActiveMedia(null)}>
        <DialogContent className="max-w-4xl bg-card p-4 max-h-[90vh] overflow-y-auto">
          {activeMedia && (
            <div className="space-y-3">
              <div className="text-sm font-semibold text-card-foreground">
                {activeMedia.label ?? activeMedia.type}
              </div>
              {activeMedia.type === 'video' ? (
                <video controls className="w-full max-h-[75vh] rounded-lg object-contain">
                  <source src={activeMedia.url} />
                </video>
              ) : (
                <img
                  src={activeMedia.url}
                  alt={activeMedia.label ?? 'Run media'}
                  className="w-full max-h-[75vh] rounded-lg object-contain"
                />
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/50 px-3 py-2">
      <span className="text-muted-foreground block mb-0.5">{label}</span>
      <span className="font-medium text-card-foreground">{value}</span>
    </div>
  );
}

type BadgeStatus = 'Running' | 'Completed' | 'Failed';

function toBadgeStatus(status: string): BadgeStatus {
  const normalized = status.toLowerCase();
  if (normalized === 'failed' || normalized === 'error') {
    return 'Failed';
  }
  if (normalized === 'completed' || normalized === 'success') {
    return 'Completed';
  }
  return 'Running';
}

function normalizeResult(result: string | null | undefined, issueCount: number) {
  if (!result) {
    return issueCount > 0 ? 'Issue found' : 'No issues';
  }
  const normalized = result.toLowerCase();
  if (normalized === 'issue_found') {
    return 'Issue found';
  }
  if (normalized === 'no_issues') {
    return 'No issues';
  }
  if (normalized === 'crash') {
    return 'Crash';
  }
  return result.replace(/_/g, ' ');
}

function normalizeLocale(locale: string | null | undefined) {
  if (!locale) {
    return '—';
  }
  const normalized = locale.toLowerCase();
  if (normalized === 'en-us' || normalized === 'en') {
    return 'EN';
  }
  return locale;
}

function formatStartedAt(value?: string | null) {
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

function normalizeIssueStatus(status: string) {
  return status
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default Runs;
