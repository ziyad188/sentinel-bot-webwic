import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Smartphone, Wifi, Globe, User } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useRunConfig } from '@/lib/run-config';
import { useProjectSelection } from '@/lib/project';
import { RunStatusBadge } from '@/components/StatusBadge';

type DeviceOption = {
  id: string;
  name: string;
};

type DeviceListResponse = {
  items: DeviceOption[];
  total: number;
  page: number;
  page_size: number;
};

type NetworkOption = {
  id: string;
  name: string;
};

type NetworkListResponse = {
  items: NetworkOption[];
  total: number;
  page: number;
  page_size: number;
};

type RunListItem = {
  id: string;
  display_id?: string | null;
  started_at?: string | null;
  device_name?: string | null;
  network_name?: string | null;
  status: string;
};

type RunListResponse = {
  items: RunListItem[];
  total: number;
  page: number;
  page_size: number;
};

const DEVICE_PAGE_SIZE = 20;
const NETWORK_PAGE_SIZE = 20;

export function LiveRunPanel() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { runConfig, setRunConfig } = useRunConfig();
  const { selectedProjectId } = useProjectSelection();

  const [device, setDevice] = useState(runConfig.deviceId);
  const [devices, setDevices] = useState<DeviceOption[]>([]);
  const [devicePage, setDevicePage] = useState(0);
  const [deviceTotal, setDeviceTotal] = useState(0);
  const [deviceOpen, setDeviceOpen] = useState(false);
  const [isLoadingDevices, setIsLoadingDevices] = useState(false);
  const [deviceError, setDeviceError] = useState<string | null>(null);
  const [hasFetchedDevices, setHasFetchedDevices] = useState(false);

  const [network, setNetwork] = useState(runConfig.networkId);
  const [networks, setNetworks] = useState<NetworkOption[]>([]);
  const [networkPage, setNetworkPage] = useState(0);
  const [networkTotal, setNetworkTotal] = useState(0);
  const [networkOpen, setNetworkOpen] = useState(false);
  const [isLoadingNetworks, setIsLoadingNetworks] = useState(false);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [hasFetchedNetworks, setHasFetchedNetworks] = useState(false);
  const [persona, setPersona] = useState(runConfig.persona);
  const [inputJson, setInputJson] = useState(runConfig.inputJson ?? '');
  const locale = 'EN';

  const [runItems, setRunItems] = useState<RunListItem[]>([]);
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const runFetchRef = useRef(false);

  const hasMoreDevices = devicePage === 0 ? true : devices.length < deviceTotal;
  const hasMoreNetworks = networkPage === 0 ? true : networks.length < networkTotal;

  useEffect(() => {
    if (!runConfig.locale) {
      setRunConfig({ locale: 'en-US' });
    }
    if (!runConfig.persona) {
      setRunConfig({ persona: 'first_time_user' });
    }
  }, [runConfig.locale, runConfig.persona, setRunConfig]);

  useEffect(() => {
    setPersona(runConfig.persona);
  }, [runConfig.persona]);

  useEffect(() => {
    setInputJson(runConfig.inputJson ?? '');
  }, [runConfig.inputJson]);

  useEffect(() => {
    setRunConfig({ deviceId: device });
  }, [device, setRunConfig]);

  useEffect(() => {
    setRunConfig({ networkId: network });
  }, [network, setRunConfig]);

  useEffect(() => {
    setRunConfig({ persona });
  }, [persona, setRunConfig]);

  useEffect(() => {
    setRunConfig({ inputJson });
  }, [inputJson, setRunConfig]);

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

  const fetchDevices = useCallback(async (page: number) => {
    if (isLoadingDevices) {
      return;
    }

    try {
      setIsLoadingDevices(true);
      setDeviceError(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(DEVICE_PAGE_SIZE),
      });

      const response = await requestWithSession(`/list/devices?${params.toString()}`);
      if (!response) {
        setDeviceError('Session expired.');
        return;
      }

      if (!response.ok) {
        setDeviceError('Unable to load devices.');
        toast({
          variant: 'destructive',
          title: 'Device list failed',
          description: 'We could not load devices. Try again.',
        });
        return;
      }

      const data = (await response.json()) as DeviceListResponse;
      const nextItems = data.items ?? [];
      const seen = new Set<string>();
      const merged: DeviceOption[] = [];
      for (const item of [...devices, ...nextItems]) {
        if (seen.has(item.id)) {
          continue;
        }
        seen.add(item.id);
        merged.push(item);
      }
      setDevices(merged);
      setDeviceTotal(data.total ?? merged.length);
      setDevicePage(data.page ?? page);

      if (merged.length > 0) {
        const hasSelected = merged.some((item) => item.id === device);
        if (!device || !hasSelected) {
          setDevice(merged[0].id);
        }
      }
    } catch (error) {
      setDeviceError('Unable to load devices.');
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    } finally {
      setIsLoadingDevices(false);
    }
  }, [device, devices, isLoadingDevices, requestWithSession, toast]);

  const fetchNetworks = useCallback(async (page: number) => {
    if (isLoadingNetworks) {
      return;
    }

    try {
      setIsLoadingNetworks(true);
      setNetworkError(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(NETWORK_PAGE_SIZE),
      });

      const response = await requestWithSession(`/list/networks?${params.toString()}`);
      if (!response) {
        setNetworkError('Session expired.');
        return;
      }

      if (!response.ok) {
        setNetworkError('Unable to load networks.');
        toast({
          variant: 'destructive',
          title: 'Network list failed',
          description: 'We could not load networks. Try again.',
        });
        return;
      }

      const data = (await response.json()) as NetworkListResponse;
      const nextItems = data.items ?? [];
      const seen = new Set<string>();
      const merged: NetworkOption[] = [];
      for (const item of [...networks, ...nextItems]) {
        if (seen.has(item.id)) {
          continue;
        }
        seen.add(item.id);
        merged.push(item);
      }
      setNetworks(merged);
      setNetworkTotal(data.total ?? merged.length);
      setNetworkPage(data.page ?? page);

      if (merged.length > 0) {
        const hasSelected = merged.some((item) => item.id === network);
        if (!network || !hasSelected) {
          setNetwork(merged[0].id);
        }
      }
    } catch (error) {
      setNetworkError('Unable to load networks.');
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    } finally {
      setIsLoadingNetworks(false);
    }
  }, [isLoadingNetworks, network, networks, requestWithSession, toast]);

  const fetchRuns = useCallback(async () => {
    if (!selectedProjectId) {
      setRunItems([]);
      setRunError(null);
      return;
    }

    if (runFetchRef.current) {
      return;
    }

    try {
      runFetchRef.current = true;
      setIsLoadingRuns(true);
      setRunError(null);

      const params = new URLSearchParams({
        project_id: selectedProjectId,
        status: 'running',
        page: '1',
        page_size: '5',
      });

      const response = await requestWithSession(`/runs?${params.toString()}`);
      if (!response) {
        setRunError('Session expired.');
        return;
      }

      if (!response.ok) {
        setRunError('Unable to load current runs.');
        toast({
          variant: 'destructive',
          title: 'Runs failed',
          description: 'We could not load current runs. Try again.',
        });
        return;
      }

      const data = (await response.json()) as RunListResponse;
      setRunItems(data.items ?? []);
    } catch (error) {
      setRunError('Unable to load current runs.');
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    } finally {
      runFetchRef.current = false;
      setIsLoadingRuns(false);
    }
  }, [requestWithSession, selectedProjectId, toast]);

  useEffect(() => {
    if (deviceOpen && !hasFetchedDevices && !isLoadingDevices && !deviceError) {
      void fetchDevices(1);
      setHasFetchedDevices(true);
    }
  }, [deviceError, deviceOpen, fetchDevices, hasFetchedDevices, isLoadingDevices]);

  useEffect(() => {
    if (networkOpen && !hasFetchedNetworks && !isLoadingNetworks && !networkError) {
      void fetchNetworks(1);
      setHasFetchedNetworks(true);
    }
  }, [fetchNetworks, hasFetchedNetworks, isLoadingNetworks, networkError, networkOpen]);

  useEffect(() => {
    if (!hasFetchedDevices && !isLoadingDevices && !deviceError) {
      void fetchDevices(1);
      setHasFetchedDevices(true);
    }
  }, [deviceError, fetchDevices, hasFetchedDevices, isLoadingDevices]);

  useEffect(() => {
    if (!hasFetchedNetworks && !isLoadingNetworks && !networkError) {
      void fetchNetworks(1);
      setHasFetchedNetworks(true);
    }
  }, [fetchNetworks, hasFetchedNetworks, isLoadingNetworks, networkError]);

  useEffect(() => {
    void fetchRuns();
  }, [fetchRuns, selectedProjectId]);

  const handleDeviceScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    const distanceFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
    if (distanceFromBottom < 24 && hasMoreDevices && !isLoadingDevices && !deviceError) {
      void fetchDevices(devicePage + 1);
    }
  };

  const handleNetworkScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    const distanceFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
    if (distanceFromBottom < 24 && hasMoreNetworks && !isLoadingNetworks && !networkError) {
      void fetchNetworks(networkPage + 1);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h3 className="text-sm font-semibold text-card-foreground">Live Run</h3>
        <span className="inline-flex items-center gap-1.5 text-xs text-status-running font-medium">
          <span className="h-1.5 w-1.5 rounded-full bg-status-running animate-pulse-dot" />
          Running
        </span>
      </div>

      <div className="p-5 space-y-5">
        {/* Current Runs */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Current runs</h4>
            {selectedProjectId && (
              <span className="text-[10px] text-muted-foreground">
                {isLoadingRuns ? 'Loading...' : `${runItems.length} running`}
              </span>
            )}
          </div>
          <div className="space-y-2">
            {runItems.map((run) => (
              <div key={run.id} className="rounded-lg border border-border bg-muted/40 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-card-foreground">{run.display_id ?? run.id}</p>
                    <p className="text-[10px] text-muted-foreground">{formatStartedAt(run.started_at)}</p>
                  </div>
                  <RunStatusBadge status={toBadgeStatus(run.status)} />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Smartphone className="h-3 w-3" />
                    {run.device_name ?? '—'}
                  </span>
                  <span className="flex items-center gap-1">
                    <Wifi className="h-3 w-3" />
                    {run.network_name ?? '—'}
                  </span>
                </div>
              </div>
            ))}
            {!selectedProjectId && (
              <div className="rounded-lg border border-dashed border-border px-3 py-4 text-xs text-muted-foreground">
                Select a project to view current runs.
              </div>
            )}
            {selectedProjectId && runItems.length === 0 && !isLoadingRuns && (
              <div className="rounded-lg border border-dashed border-border px-3 py-4 text-xs text-muted-foreground">
                {runError ?? 'No runs are currently active.'}
              </div>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="border-t border-border pt-4 space-y-3">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Configuration</h4>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1.5"><Smartphone className="h-3 w-3" /> Device</Label>
              <Select value={device} onValueChange={setDevice} onOpenChange={setDeviceOpen}>
                <SelectTrigger className="h-8 text-xs bg-card">
                  <SelectValue placeholder={isLoadingDevices ? "Loading devices..." : "Select device"} />
                </SelectTrigger>
                <SelectContent
                  className="bg-popover"
                  viewportClassName="max-h-64"
                  viewportProps={{ onScroll: handleDeviceScroll }}
                >
                  {devices.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.name}
                    </SelectItem>
                  ))}
                  {isLoadingDevices && (
                    <SelectItem value="__loading" disabled>
                      Loading devices...
                    </SelectItem>
                  )}
                  {!isLoadingDevices && deviceError && (
                    <SelectItem value="__error" disabled>
                      {deviceError}
                    </SelectItem>
                  )}
                  {!isLoadingDevices && !deviceError && devices.length === 0 && (
                    <SelectItem value="__empty" disabled>
                      No devices found
                    </SelectItem>
                  )}
                  {!isLoadingDevices && hasMoreDevices && devices.length > 0 && (
                    <SelectItem value="__more" disabled>
                      Scroll to load more
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1.5"><Wifi className="h-3 w-3" /> Network</Label>
              <Select value={network} onValueChange={setNetwork} onOpenChange={setNetworkOpen}>
                <SelectTrigger className="h-8 text-xs bg-card">
                  <SelectValue placeholder={isLoadingNetworks ? "Loading networks..." : "Select network"} />
                </SelectTrigger>
                <SelectContent
                  className="bg-popover"
                  viewportClassName="max-h-64"
                  viewportProps={{ onScroll: handleNetworkScroll }}
                >
                  {networks.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.name}
                    </SelectItem>
                  ))}
                  {isLoadingNetworks && (
                    <SelectItem value="__loading-network" disabled>
                      Loading networks...
                    </SelectItem>
                  )}
                  {!isLoadingNetworks && networkError && (
                    <SelectItem value="__error-network" disabled>
                      {networkError}
                    </SelectItem>
                  )}
                  {!isLoadingNetworks && !networkError && networks.length === 0 && (
                    <SelectItem value="__empty-network" disabled>
                      No networks found
                    </SelectItem>
                  )}
                  {!isLoadingNetworks && hasMoreNetworks && networks.length > 0 && (
                    <SelectItem value="__more-network" disabled>
                      Scroll to load more
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1.5"><Globe className="h-3 w-3" /> Locale</Label>
              <Select value={locale} disabled>
                <SelectTrigger className="h-8 text-xs bg-card">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover">
                  <SelectItem value="EN">EN</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs flex items-center gap-1.5"><User className="h-3 w-3" /> Persona</Label>
              <Select value={persona} onValueChange={setPersona}>
                <SelectTrigger className="h-8 text-xs bg-card">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover">
                  <SelectItem value="first_time_user">First-time user</SelectItem>
                  <SelectItem value="power_user">Power user</SelectItem>
                  <SelectItem value="elderly_user">Elderly user</SelectItem>
                  <SelectItem value="non_technical_user">Non-technical user</SelectItem>
                  <SelectItem value="impatient_user">Impatient user</SelectItem>
                  <SelectItem value="adversarial_user">Adversarial user</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5 col-span-2">
              <Label className="text-xs">Input JSON</Label>
              <Textarea
                value={inputJson}
                onChange={(event) => setInputJson(event.target.value)}
                placeholder='{"key":"value"}'
                className="min-h-[96px] text-xs bg-card"
              />
              <p className="text-[10px] text-muted-foreground">Add key-value JSON input for the run.</p>
            </div>
          </div>
        </div>
      </div>
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
