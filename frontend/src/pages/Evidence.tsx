import { useCallback, useEffect, useRef, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Image, Video, Smartphone, Clock } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useNavigate } from 'react-router-dom';
import { useProjectSelection } from '@/lib/project';

type EvidenceItem = {
  id: string;
  project_id: string;
  run_id: string;
  issue_id?: string | null;
  issue_title?: string | null;
  type: 'screenshot' | 'video';
  storage_path?: string | null;
  label?: string | null;
  created_at?: string | null;
  device_id?: string | null;
  device_name?: string | null;
  url: string;
};

type EvidenceResponse = {
  items: EvidenceItem[];
  total: number;
  page: number;
  page_size: number;
};

const Evidence = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelection();
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [selectedItem, setSelectedItem] = useState<EvidenceItem | null>(null);
  const [items, setItems] = useState<EvidenceItem[]>([]);
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

  const fetchEvidence = useCallback(
    async (requestedPage: number) => {
      if (!selectedProjectId) {
        setItems([]);
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

        if (typeFilter !== 'all') {
          params.set('media_type', typeFilter);
        }

        const response = await requestWithSession(`/evidence?${params.toString()}`);
        if (!response) {
          setErrorMessage('Session expired.');
          return;
        }

        if (!response.ok) {
          setErrorMessage('Unable to load evidence.');
          toast({
            variant: 'destructive',
            title: 'Evidence failed',
            description: 'We could not load evidence. Try again.',
          });
          return;
        }

        const data = (await response.json()) as EvidenceResponse;
        const list = data.items ?? [];
        setItems(list);
        setTotal(data.total ?? list.length);
        setPage(data.page ?? requestedPage);
        setPageSize(data.page_size ?? pageSize);
      } catch (error) {
        setErrorMessage('Unable to load evidence.');
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
    [pageSize, requestWithSession, selectedProjectId, toast, typeFilter],
  );

  useEffect(() => {
    setPage(1);
    if (selectedProjectId) {
      void fetchEvidence(1);
    }
  }, [fetchEvidence, selectedProjectId, typeFilter]);

  const handlePageChange = (nextPage: number) => {
    if (isLoading) {
      return;
    }
    const target = Math.min(Math.max(nextPage, 1), totalPages);
    setPage(target);
    void fetchEvidence(target);
  };

  return (
    <div className="space-y-6 max-w-[1400px]">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Evidence</h1>
        <p className="mt-1 text-sm text-muted-foreground">Screenshots and recordings captured during agent runs.</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Select value={typeFilter} onValueChange={setTypeFilter} disabled={!selectedProjectId}>
          <SelectTrigger className="w-40 h-9 text-xs bg-card"><SelectValue placeholder="Type" /></SelectTrigger>
          <SelectContent className="bg-popover">
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="screenshot">Screenshots</SelectItem>
            <SelectItem value="video">Videos</SelectItem>
          </SelectContent>
        </Select>
        {!selectedProjectId && (
          <span className="text-xs text-muted-foreground self-center">
            Select a project to view evidence.
          </span>
        )}
      </div>

      {/* Gallery Grid */}
      <div className="grid grid-cols-4 gap-4">
        {items.map((item) => (
          <div
            key={item.id}
            className="group rounded-xl border border-border bg-card shadow-sm overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
            onClick={() => setSelectedItem(item)}
          >
            <div className="relative aspect-video bg-muted">
              {item.type === 'video' ? (
                <video className="h-full w-full object-cover" muted playsInline preload="metadata">
                  <source src={item.url} />
                </video>
              ) : (
                <img src={item.url} alt={item.label ?? 'Evidence'} className="h-full w-full object-cover" />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
              <div className="absolute bottom-2 left-2 text-[10px] font-semibold text-white/90">
                {item.label ?? item.type}
              </div>
            </div>
            <div className="p-3">
              <p className="text-xs font-medium text-card-foreground truncate">{item.issue_title ?? 'Unlinked evidence'}</p>
              <div className="flex items-center gap-2 mt-1.5 text-[10px] text-muted-foreground">
                <span className="flex items-center gap-1">
                  {item.type === 'screenshot' ? <Image className="h-3 w-3" /> : <Video className="h-3 w-3" />}
                  {item.type}
                </span>
                <span>{item.device_name ?? '—'}</span>
              </div>
            </div>
          </div>
        ))}
        {items.length === 0 && !isLoading && (
          <div className="col-span-full text-sm text-muted-foreground">
            {errorMessage ?? (selectedProjectId ? 'No evidence found for this project.' : 'Select a project to view evidence.')}
          </div>
        )}
        {isLoading && (
          <div className="col-span-full text-sm text-muted-foreground">Loading evidence...</div>
        )}
      </div>

      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            Page {page} of {totalPages} · {total} items
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

      {/* Viewer Modal */}
      <Dialog open={!!selectedItem} onOpenChange={() => setSelectedItem(null)}>
        <DialogContent className="max-w-4xl bg-card p-4 max-h-[90vh] overflow-y-auto">
          {selectedItem && (
            <>
              <DialogHeader>
                <DialogTitle className="text-sm font-semibold">{selectedItem.label ?? selectedItem.type}</DialogTitle>
              </DialogHeader>
              <div className="mt-4 space-y-4">
                <div className="rounded-lg bg-muted">
                  {selectedItem.type === 'video' ? (
                    <video controls className="w-full max-h-[70vh] rounded-lg object-contain">
                      <source src={selectedItem.url} />
                    </video>
                  ) : (
                    <img
                      src={selectedItem.url}
                      alt={selectedItem.label ?? 'Evidence'}
                      className="w-full max-h-[70vh] rounded-lg object-contain"
                    />
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="rounded-lg border border-border bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground block mb-0.5">Type</span>
                    <span className="font-medium text-card-foreground capitalize">{selectedItem.type}</span>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground block mb-0.5">Run ID</span>
                    <span className="font-medium text-card-foreground font-mono">{selectedItem.run_id}</span>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground block mb-0.5 flex items-center gap-1"><Smartphone className="h-3 w-3" /> Device</span>
                    <span className="font-medium text-card-foreground">{selectedItem.device_name ?? '—'}</span>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground block mb-0.5 flex items-center gap-1"><Clock className="h-3 w-3" /> Timestamp</span>
                    <span className="font-medium text-card-foreground">{formatDate(selectedItem.created_at)}</span>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/50 px-3 py-2 col-span-2">
                    <span className="text-muted-foreground block mb-0.5">Issue</span>
                    <span className="font-medium text-card-foreground">{selectedItem.issue_title ?? '—'}</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

const formatDate = (value?: string | null) => {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default Evidence;
