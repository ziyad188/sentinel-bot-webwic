import { useCallback, useEffect, useMemo, useState } from 'react';
import { FolderPlus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { useNavigate } from 'react-router-dom';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useProjectSelection } from '@/lib/project';

type Project = {
  id: string;
  name: string;
  environment: string;
  targetUrl?: string;
};

export function TopBar() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const { selectedProjectId, setSelectedProjectId } = useProjectSelection();
  const [projectPage, setProjectPage] = useState(0);
  const [projectTotal, setProjectTotal] = useState(0);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [hasFetchedProjects, setHasFetchedProjects] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectEnvironment, setProjectEnvironment] = useState('development');
  const [projectUrl, setProjectUrl] = useState('');

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId),
    [projects, selectedProjectId],
  );

  const hasMoreProjects = projectPage === 0 ? true : projects.length < projectTotal;

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

  const fetchProjects = useCallback(async (page: number) => {
    if (isLoadingProjects) {
      return;
    }

    try {
      setIsLoadingProjects(true);
      setProjectError(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(20),
      });

      const response = await requestWithSession(`/list/projects?${params.toString()}`);
      if (!response) {
        setProjectError('Session expired.');
        return;
      }

      if (!response.ok) {
        setProjectError('Unable to load projects.');
        toast({
          variant: 'destructive',
          title: 'Project list failed',
          description: 'We could not load projects. Try again.',
        });
        return;
      }

      const data = (await response.json()) as {
        items: Project[];
        total: number;
        page: number;
        page_size: number;
      };

      const nextItems = data.items ?? [];
      const seen = new Set<string>();
      const merged: Project[] = [];
      for (const item of [...projects, ...nextItems]) {
        if (seen.has(item.id)) {
          continue;
        }
        seen.add(item.id);
        merged.push(item);
      }
      setProjects(merged);
      setProjectTotal(data.total ?? merged.length);
      setProjectPage(data.page ?? page);

      if (merged.length > 0) {
        const hasSelected = merged.some((project) => project.id === selectedProjectId);
        if (!selectedProjectId || !hasSelected) {
          setSelectedProjectId(merged[0].id);
        }
      }
    } catch (error) {
      setProjectError('Unable to load projects.');
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    } finally {
      setIsLoadingProjects(false);
    }
  }, [isLoadingProjects, projects, requestWithSession, selectedProjectId, toast]);

  const handleProjectScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    const distanceFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
    if (distanceFromBottom < 24 && hasMoreProjects && !isLoadingProjects && !projectError) {
      void fetchProjects(projectPage + 1);
    }
  };

  const handleCreateProject = async () => {
    const trimmedName = projectName.trim();
    const trimmedUrl = projectUrl.trim();

    if (!trimmedName || !trimmedUrl) {
      toast({
        variant: 'destructive',
        title: 'Missing details',
        description: 'Enter a project name and URL.',
      });
      return;
    }

    if (!/^https:\/\//i.test(trimmedUrl)) {
      toast({
        variant: 'destructive',
        title: 'Invalid URL',
        description: 'Target URL must start with https://',
      });
      return;
    }

    try {
      const response = await requestWithSession('/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: trimmedName,
          environment: projectEnvironment,
          target_url: trimmedUrl,
        }),
      });

      if (!response) {
        return;
      }

      if (!response.ok) {
        toast({
          variant: 'destructive',
          title: 'Project create failed',
          description: 'Unable to create the project. Try again.',
        });
        return;
      }

      const created = (await response.json()) as {
        id: string;
        name: string;
        environment: string;
        target_url: string;
      };

      const newProject: Project = {
        id: created.id,
        name: created.name,
        environment: created.environment,
        targetUrl: created.target_url,
      };

      setProjects((prev) => [newProject, ...prev]);
      setSelectedProjectId(newProject.id);
      setProjectName('');
      setProjectUrl('');
      setIsDialogOpen(false);
      toast({
        title: 'Project created',
        description: `${newProject.name} is ready to monitor.`,
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    }
  };

  const projectLabel = selectedProject
    ? `${selectedProject.name} · ${selectedProject.environment}`
    : undefined;

  const handleProjectOpen = (open: boolean) => {
    if (open && projects.length === 0 && !isLoadingProjects && !projectError) {
      void fetchProjects(1);
    }
  };

  useEffect(() => {
    if (!hasFetchedProjects && !isLoadingProjects && !projectError) {
      void fetchProjects(1);
      setHasFetchedProjects(true);
    }
  }, [fetchProjects, hasFetchedProjects, isLoadingProjects, projectError]);

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-6">
      <div className="flex items-center gap-3">
        <Select value={selectedProjectId} onValueChange={setSelectedProjectId} onOpenChange={handleProjectOpen}>
          <SelectTrigger className="h-9 min-w-[220px] text-xs bg-background">
            <SelectValue placeholder="Select a project">
              {projectLabel}
            </SelectValue>
          </SelectTrigger>
          <SelectContent className="bg-popover" viewportClassName="max-h-64" viewportProps={{ onScroll: handleProjectScroll }}>
            {projects.map((project) => (
              <SelectItem key={project.id} value={project.id}>
                {project.name} · {project.environment}
              </SelectItem>
            ))}
            {isLoadingProjects && (
              <SelectItem value="__loading-projects" disabled>
                Loading projects...
              </SelectItem>
            )}
            {!isLoadingProjects && projectError && (
              <SelectItem value="__error-projects" disabled>
                {projectError}
              </SelectItem>
            )}
            {!isLoadingProjects && !projectError && projects.length === 0 && (
              <SelectItem value="__empty-projects" disabled>
                No projects found
              </SelectItem>
            )}
            {!isLoadingProjects && hasMoreProjects && projects.length > 0 && (
              <SelectItem value="__more-projects" disabled>
                Scroll to load more
              </SelectItem>
            )}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" className="gap-2" onClick={() => setIsDialogOpen(true)}>
          <FolderPlus className="h-4 w-4" />
          New project
        </Button>
      </div>

      <div />

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create project</DialogTitle>
            <DialogDescription>Give your project a name and the URL to monitor.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="project-name">Project name</Label>
              <Input
                id="project-name"
                placeholder="Signup monitoring"
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-environment">Environment</Label>
              <Select value={projectEnvironment} onValueChange={setProjectEnvironment}>
                <SelectTrigger id="project-environment" className="bg-background">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover">
                  <SelectItem value="development">Development</SelectItem>
                  <SelectItem value="testing">Testing</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-url">Target URL</Label>
              <Input
                id="project-url"
                placeholder="https://app.yourcompany.com/signup"
                value={projectUrl}
                onChange={(event) => setProjectUrl(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">Must start with https://</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateProject}>Create project</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </header>
  );
}
