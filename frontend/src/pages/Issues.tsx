import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { SeverityBadge, CategoryBadge, IssueStatusBadge } from '@/components/StatusBadge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ExternalLink, Smartphone, Wifi, Globe } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useNavigate } from 'react-router-dom';
import { useProjectSelection } from '@/lib/project';

type IssueListItem = {
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
  run_id?: string | null;
  slack_url?: string | null;
  slack_user_id?: string | null;
  slack_display_name?: string | null;
  slack_real_name?: string | null;
  slack_email?: string | null;
  slack_avatar_url?: string | null;
  device_id?: string | null;
  device_name?: string | null;
  network_id?: string | null;
  network_name?: string | null;
  locale?: string | null;
};

type IssueListResponse = {
  items: IssueListItem[];
  total: number;
  page: number;
  page_size: number;
};

type IssueMedia = {
  id: string;
  issue_id: string;
  type: string;
  storage_path?: string | null;
  label?: string | null;
  created_at?: string | null;
  url: string;
};

type IssueDetailResponse = {
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
  run_id?: string | null;
  run_display_id?: string | null;
  slack_url?: string | null;
  slack_user_id?: string | null;
  owner_name?: string | null;
  media: IssueMedia[];
};

const columns = ['Investigating', 'Assigned', 'Resolved'] as const;
type IssueColumn = typeof columns[number];

const Issues = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelection();
  const [selectedIssue, setSelectedIssue] = useState<IssueListItem | null>(null);
  const [statusSelection, setStatusSelection] = useState<IssueColumn>('Investigating');
  const [isUpdatingIssue, setIsUpdatingIssue] = useState(false);
  const [issues, setIssues] = useState<IssueListItem[]>([]);
  const [detailsByIssueId, setDetailsByIssueId] = useState<Record<string, IssueDetailResponse>>({});
  const [detailsLoadingId, setDetailsLoadingId] = useState<string | null>(null);
  const [activeMedia, setActiveMedia] = useState<IssueMedia | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const isFetchingRef = useRef(false);

  const effectivePageSize = pageSize || 25;
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

  const fetchIssues = useCallback(
    async (requestedPage: number) => {
      if (!selectedProjectId) {
        setIssues([]);
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

        if (severityFilter !== 'all') {
          params.set('severity', severityFilter.toUpperCase());
        }

        const response = await requestWithSession(`/issues?${params.toString()}`);
        if (!response) {
          setErrorMessage('Session expired.');
          return;
        }

        if (!response.ok) {
          setErrorMessage('Unable to load issues.');
          toast({
            variant: 'destructive',
            title: 'Issues failed',
            description: 'We could not load issues. Try again.',
          });
          return;
        }

        const data = (await response.json()) as IssueListResponse;
        const items = data.items ?? [];
        setIssues(items);
        setTotal(data.total ?? items.length);
        setPage(data.page ?? requestedPage);
        setPageSize(data.page_size ?? pageSize);
      } catch (error) {
        setErrorMessage('Unable to load issues.');
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
    [pageSize, requestWithSession, selectedProjectId, severityFilter, toast],
  );

  const updateIssueStatus = useCallback(
    async (issueId: string, nextStatus: IssueColumn) => {
      if (isUpdatingIssue) {
        return;
      }

      try {
        setIsUpdatingIssue(true);
        const response = await requestWithSession(`/issues/${issueId}/status`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ status: nextStatus.toLowerCase() }),
        });

        if (!response) {
          return;
        }

        if (!response.ok) {
          toast({
            variant: 'destructive',
            title: 'Update failed',
            description: 'Unable to update the issue status. Try again.',
          });
          return;
        }

        const data = (await response.json()) as { id: string; status: string };
        setIssues((prev) =>
          prev.map((issue) =>
            issue.id === data.id ? { ...issue, status: data.status } : issue,
          ),
        );
        setSelectedIssue((prev) =>
          prev && prev.id === data.id ? { ...prev, status: data.status } : prev,
        );

        toast({
          title: 'Status updated',
          description: `Issue moved to ${normalizeIssueStatus(data.status)}.`,
        });

        if (selectedProjectId) {
          void fetchIssues(page);
        }
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Network error',
          description: 'We could not reach the server. Try again.',
        });
      } finally {
        setIsUpdatingIssue(false);
      }
    },
    [fetchIssues, isUpdatingIssue, page, requestWithSession, selectedProjectId, toast],
  );

  const fetchIssueDetails = useCallback(
    async (issueId: string) => {
      if (!selectedProjectId || detailsLoadingId === issueId || detailsByIssueId[issueId]) {
        return;
      }

      try {
        setDetailsLoadingId(issueId);
        const params = new URLSearchParams({
          project_id: selectedProjectId,
        });

        const response = await requestWithSession(`/issues/${issueId}?${params.toString()}`);
        if (!response) {
          return;
        }

        if (!response.ok) {
          toast({
            variant: 'destructive',
            title: 'Issue details failed',
            description: 'Unable to load issue details. Try again.',
          });
          return;
        }

        const data = (await response.json()) as IssueDetailResponse;
        setDetailsByIssueId((prev) => ({ ...prev, [issueId]: data }));
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Network error',
          description: 'We could not reach the server. Try again.',
        });
      } finally {
        setDetailsLoadingId((prev) => (prev === issueId ? null : prev));
      }
    },
    [detailsByIssueId, detailsLoadingId, requestWithSession, selectedProjectId, toast],
  );

  useEffect(() => {
    setPage(1);
    if (selectedProjectId) {
      void fetchIssues(1);
    }
  }, [fetchIssues, selectedProjectId, severityFilter]);

  useEffect(() => {
    if (selectedIssue) {
      setStatusSelection(normalizeIssueStatus(selectedIssue.status));
    }
  }, [selectedIssue]);

  useEffect(() => {
    if (selectedIssue) {
      void fetchIssueDetails(selectedIssue.id);
    }
  }, [fetchIssueDetails, selectedIssue]);

  const handlePageChange = (nextPage: number) => {
    if (isLoading) {
      return;
    }
    const target = Math.min(Math.max(nextPage, 1), totalPages);
    setPage(target);
    void fetchIssues(target);
  };

  const grouped = useMemo(() => {
    return columns.reduce((acc, status) => {
      acc[status] = issues.filter((issue) => normalizeIssueStatus(issue.status) === status);
      return acc;
    }, {} as Record<IssueColumn, IssueListItem[]>);
  }, [issues]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Issues</h1>
        <p className="mt-1 text-sm text-muted-foreground">All detected issues organized by investigation status.</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
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
            Select a project to view issues.
          </span>
        )}
      </div>

      {/* Kanban Board */}
      <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-thin">
        {columns.map(status => (
          <div key={status} className="flex-shrink-0 w-72">
            <div className="flex items-center gap-2 mb-3 px-1">
              <h3 className="text-sm font-semibold text-foreground">{status}</h3>
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-muted-foreground">
                {grouped[status].length}
              </span>
            </div>
            <div className="space-y-3">
              {grouped[status].map(issue => (
                <div
                  key={issue.id}
                  className="rounded-xl border border-border bg-card p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => setSelectedIssue(issue)}
                >
                  <div className="flex items-center gap-2 mb-2">
                    {issue.severity && (
                      <SeverityBadge severity={issue.severity.toUpperCase() as 'P0' | 'P1' | 'P2' | 'P3'} />
                    )}
                    {issue.category && <CategoryBadge category={formatCategory(issue.category)} />}
                  </div>
                  <p className="text-sm font-medium text-card-foreground mb-2 line-clamp-2">{issue.title}</p>
                  <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1"><Smartphone className="h-3 w-3" />{issue.device_name ?? '—'}</span>
                    <span className="flex items-center gap-1"><Wifi className="h-3 w-3" />{issue.network_name ?? '—'}</span>
                    <span className="flex items-center gap-1"><Globe className="h-3 w-3" />{normalizeLocale(issue.locale)}</span>
                  </div>
                </div>
              ))}
              {grouped[status].length === 0 && (
                <div className="rounded-xl border border-dashed border-border p-6 text-center">
                  <p className="text-xs text-muted-foreground">
                    {isLoading ? 'Loading...' : (errorMessage ?? 'No issues')}
                  </p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            Page {page} of {totalPages} · {total} issues
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="default"
              onClick={() => handlePageChange(page - 1)}
              disabled={isLoading || page <= 1}
            >
              Previous
            </Button>
            <Button
              variant="default"
              size="default"
              onClick={() => handlePageChange(page + 1)}
              disabled={isLoading || page >= totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Issue Detail Dialog */}
      <Dialog open={!!selectedIssue} onOpenChange={() => setSelectedIssue(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto bg-card">
          {selectedIssue && (
            <>
              <DialogHeader>
                <DialogTitle className="text-lg font-bold text-card-foreground pr-8">
                  {detailsByIssueId[selectedIssue.id]?.title ?? selectedIssue.title}
                </DialogTitle>
              </DialogHeader>

              <div className="mt-4 space-y-6">
                <div className="flex items-center gap-2 flex-wrap">
                  {(detailsByIssueId[selectedIssue.id]?.severity ?? selectedIssue.severity) && (
                    <SeverityBadge
                      severity={(detailsByIssueId[selectedIssue.id]?.severity ?? selectedIssue.severity)!.toUpperCase() as
                        'P0' | 'P1' | 'P2' | 'P3'}
                    />
                  )}
                  {(detailsByIssueId[selectedIssue.id]?.category ?? selectedIssue.category) && (
                    <CategoryBadge
                      category={formatCategory(detailsByIssueId[selectedIssue.id]?.category ?? selectedIssue.category!)}
                    />
                  )}
                  <IssueStatusBadge
                    status={normalizeIssueStatus(detailsByIssueId[selectedIssue.id]?.status ?? selectedIssue.status)}
                  />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Select value={statusSelection} onValueChange={(value) => setStatusSelection(value as IssueColumn)}>
                    <SelectTrigger className="w-44 h-9 text-xs bg-card">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-popover">
                      <SelectItem value="Investigating">Investigating</SelectItem>
                      <SelectItem value="Assigned">Assigned</SelectItem>
                      <SelectItem value="Resolved">Resolved</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    onClick={() => updateIssueStatus(selectedIssue.id, statusSelection)}
                    disabled={isUpdatingIssue}
                  >
                    {isUpdatingIssue ? 'Updating...' : 'Update status'}
                  </Button>
                </div>

                {detailsLoadingId === selectedIssue.id && (
                  <div className="text-xs text-muted-foreground">Loading issue details...</div>
                )}

                {(detailsByIssueId[selectedIssue.id]?.description || selectedIssue.description) && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Description</h4>
                    <div className="rounded-lg border border-border bg-muted/50 p-4 text-sm text-card-foreground leading-relaxed">
                      {detailsByIssueId[selectedIssue.id]?.description ?? selectedIssue.description}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <MetaField label="Device" value={selectedIssue.device_name ?? '—'} />
                  <MetaField label="Network" value={selectedIssue.network_name ?? '—'} />
                  <MetaField label="Locale" value={normalizeLocale(selectedIssue.locale)} />
                  <MetaField
                    label="Run ID"
                    value={
                      detailsByIssueId[selectedIssue.id]?.run_display_id ??
                      selectedIssue.run_id ??
                      '—'
                    }
                  />
                  <MetaField
                    label="Created"
                    value={formatDate(detailsByIssueId[selectedIssue.id]?.created_at ?? selectedIssue.created_at)}
                  />
                  <MetaField
                    label="Resolved"
                    value={formatDate(detailsByIssueId[selectedIssue.id]?.resolved_at ?? selectedIssue.resolved_at)}
                  />
                  <MetaField
                    label="Assigned User"
                    value={
                      detailsByIssueId[selectedIssue.id]?.owner_name ??
                      selectedIssue.slack_display_name ??
                      '—'
                    }
                  />
                </div>

                {selectedIssue.slack_url && (
                  <Button asChild variant="outline" size="sm" className="gap-1.5 text-xs">
                    <a href={selectedIssue.slack_url} target="_blank" rel="noreferrer">
                      <ExternalLink className="h-3 w-3" /> Slack Thread Link
                    </a>
                  </Button>
                )}

                <div>
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Media</h4>
                  {detailsLoadingId === selectedIssue.id && (
                    <div className="text-xs text-muted-foreground">Loading media...</div>
                  )}
                  {detailsByIssueId[selectedIssue.id]?.media?.length ? (
                    <div className="grid grid-cols-2 gap-3">
                      {detailsByIssueId[selectedIssue.id].media.map((media) => (
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
                            <img src={media.url} alt={media.label ?? 'Issue media'} className="w-full rounded-md" />
                          )}
                        </button>
                      ))}
                    </div>
                  ) : (
                    !detailsLoadingId && (
                      <div className="text-xs text-muted-foreground">No media available for this issue.</div>
                    )
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

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
                  alt={activeMedia.label ?? 'Issue media'}
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

function normalizeIssueStatus(status?: string | null): IssueColumn | 'New' {
  const normalized = status?.toLowerCase();
  if (normalized === 'assigned') {
    return 'Assigned';
  }
  if (normalized === 'resolved') {
    return 'Resolved';
  }
  if (normalized === 'new') {
    return 'Investigating';
  }
  return 'Investigating';
}

function formatCategory(category: string) {
  return category.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeLocale(locale?: string | null) {
  if (!locale) {
    return '—';
  }
  const normalized = locale.toLowerCase();
  if (normalized === 'en-us' || normalized === 'en') {
    return 'EN';
  }
  return locale;
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

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/50 px-3 py-2">
      <span className="text-muted-foreground block mb-0.5">{label}</span>
      <span className="font-medium text-card-foreground">{value}</span>
    </div>
  );
}

export default Issues;
