import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import { clearStoredAuth, getStoredSessionRecord, isSessionExpired, refreshSession } from '@/lib/auth';
import { useNavigate } from 'react-router-dom';
import { useProjectSelection } from '@/lib/project';

type UserItem = {
  idx: number;
  id: string;
  slack_user_id: string;
  display_name: string;
  real_name: string;
  email: string;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  uuid_id: string;
  categories?: string[];
};

type UsersWithCategoriesResponse = {
  items: UserItem[];
  total: number;
  page: number;
  page_size: number;
};

const availableCategories = [
  'visual',
  'ux',
  'performance',
  'integration',
  'functional',
  'mobile',
  'accessibility',
  'frontend',
  'backend',
];

const Users = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectSelection();
  const [userList, setUserList] = useState<UserItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const isFetchingRef = useRef(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formState, setFormState] = useState({
    displayName: '',
    email: '',
    slackUserId: '',
    categories: [] as string[],
    isActive: true,
  });

  const categoriesBySlackUser = useMemo(() => {
    return userList.reduce<Record<string, string[]>>((acc, user) => {
      if (user.slack_user_id) {
        acc[user.slack_user_id] = user.categories ?? [];
      }
      return acc;
    }, {});
  }, [userList]);

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

  const fetchUsers = useCallback(
    async (requestedPage: number) => {
      if (isFetchingRef.current) {
        return;
      }

      try {
        isFetchingRef.current = true;
        setIsLoading(true);
        setErrorMessage(null);

        const params = new URLSearchParams({
          page: String(requestedPage),
          page_size: String(pageSize),
        });

        const response = await requestWithSession(`/users/with-categories?${params.toString()}`);
        if (!response) {
          setErrorMessage('Session expired.');
          return;
        }

        if (!response.ok) {
          setErrorMessage('Unable to load users.');
          toast({
            variant: 'destructive',
            title: 'Users failed',
            description: 'We could not load users. Try again.',
          });
          return;
        }

        const data = (await response.json()) as UsersWithCategoriesResponse;
        const list = data.items ?? [];
        setUserList(list);
        setTotal(data.total ?? list.length);
        setPage(data.page ?? requestedPage);
        setPageSize(data.page_size ?? pageSize);
      } catch (error) {
        setErrorMessage('Unable to load users.');
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
    [pageSize, requestWithSession, toast],
  );

  useEffect(() => {
    void fetchUsers(1);
  }, [fetchUsers]);

  const handlePageChange = (nextPage: number) => {
    if (isLoading) {
      return;
    }
    const target = Math.min(Math.max(nextPage, 1), totalPages);
    setPage(target);
    void fetchUsers(target);
  };

  const resetForm = () => {
    setFormState({
      displayName: '',
      email: '',
      slackUserId: '',
      categories: [],
      isActive: true,
    });
    setFormError(null);
  };

  const handleCreateContact = async () => {
    const displayName = formState.displayName.trim();
    const email = formState.email.trim();
    const slackUserId = formState.slackUserId.trim();
    const selectedCategories = formState.categories;

    if (!displayName || !email) {
      setFormError('Name and email are required.');
      return;
    }

    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setFormError('Enter a valid email address.');
      return;
    }

    if (selectedCategories.length > 0 && !slackUserId) {
      setFormError('Slack user ID is required when assigning a category.');
      return;
    }

    if (!selectedProjectId) {
      setFormError('Select a project before creating a contact.');
      return;
    }

    try {
      setFormError(null);
      const response = await requestWithSession('/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          slack_user_id: slackUserId || null,
          name: displayName,
          email,
          is_active: formState.isActive,
          project_id: selectedProjectId,
          categories: selectedCategories,
        }),
      });

      if (!response) {
        return;
      }

      if (!response.ok) {
        setFormError('Unable to create contact.');
        toast({
          variant: 'destructive',
          title: 'Create failed',
          description: 'We could not create the contact. Try again.',
        });
        return;
      }

      toast({
        title: 'Contact created',
        description: 'The new contact is now available.',
      });
      setIsDialogOpen(false);
      resetForm();
      void fetchUsers(1);
    } catch (error) {
      setFormError('Unable to create contact.');
      toast({
        variant: 'destructive',
        title: 'Network error',
        description: 'We could not reach the server. Try again.',
      });
    }
  };

  return (
    <div className="space-y-6 max-w-[1400px]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Users</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Current team members and category ownership across the project.
          </p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={(open) => {
          setIsDialogOpen(open);
          if (!open) {
            resetForm();
          }
        }}>
          <Button onClick={() => setIsDialogOpen(true)}>Create contact</Button>
          <DialogContent className="bg-card">
            <DialogHeader>
              <DialogTitle>Create contact</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="contact-name">Full name</Label>
                <Input
                  id="contact-name"
                  value={formState.displayName}
                  onChange={(event) => setFormState((prev) => ({ ...prev, displayName: event.target.value }))}
                  placeholder="e.g. Rihan Sajeer"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact-email">Email</Label>
                <Input
                  id="contact-email"
                  type="email"
                  value={formState.email}
                  onChange={(event) => setFormState((prev) => ({ ...prev, email: event.target.value }))}
                  placeholder="name@company.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact-slack">Slack user ID</Label>
                <Input
                  id="contact-slack"
                  value={formState.slackUserId}
                  onChange={(event) => setFormState((prev) => ({ ...prev, slackUserId: event.target.value }))}
                  placeholder="U0ADY8KSX09"
                />
              </div>
              <div className="space-y-2">
                <Label>Categories (optional)</Label>
                <div className="rounded-lg border border-border p-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    {availableCategories.map((category) => {
                      const isChecked = formState.categories.includes(category);
                      return (
                        <label key={category} className="flex items-center gap-2 text-sm text-foreground">
                          <Checkbox
                            checked={isChecked}
                            onCheckedChange={(checked) => {
                              setFormState((prev) => {
                                const next = new Set(prev.categories);
                                if (checked) {
                                  next.add(category);
                                } else {
                                  next.delete(category);
                                }
                                return { ...prev, categories: Array.from(next) };
                              });
                            }}
                          />
                          <span className="capitalize">{category}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-foreground">Active</p>
                  <p className="text-xs text-muted-foreground">Mark this contact as active.</p>
                </div>
                <Switch
                  checked={formState.isActive}
                  onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, isActive: checked }))}
                />
              </div>
              {formError && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {formError}
                </div>
              )}
            </div>
            <DialogFooter className="mt-2">
              <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateContact}>Create contact</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <section className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h2 className="text-sm font-semibold text-foreground">Team members</h2>
            <p className="text-xs text-muted-foreground">Active and inactive accounts.</p>
          </div>
          <span className="text-xs text-muted-foreground">{total || userList.length} total</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">User</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Slack</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Category</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Created</th>
              </tr>
            </thead>
            <tbody>
              {userList.map((user) => {
                const userCategories = categoriesBySlackUser[user.slack_user_id] ?? [];
                return (
                  <tr key={user.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar className="h-9 w-9">
                          {user.avatar_url ? (
                            <AvatarImage src={user.avatar_url} alt={user.display_name} />
                          ) : null}
                          <AvatarFallback className="text-xs font-semibold">
                            {user.display_name
                              .split(' ')
                              .map((part) => part[0])
                              .join('')
                              .slice(0, 2)
                              .toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <div className="text-sm font-medium text-foreground">{user.display_name}</div>
                          <div className="text-xs text-muted-foreground">{user.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <span className="font-mono">{user.slack_user_id || '—'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {userCategories.length > 0 ? (
                          userCategories.map((category) => (
                            <span
                              key={category}
                              className="inline-flex items-center rounded-full bg-muted px-2.5 py-1 text-[10px] font-semibold text-foreground"
                            >
                              {category}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                          user.is_active
                            ? 'bg-status-success/10 text-status-success'
                            : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(user.created_at)}</td>
                  </tr>
                );
              })}
              {userList.length === 0 && !isLoading && (
                <tr>
                  <td className="px-4 py-6 text-sm text-muted-foreground" colSpan={5}>
                    {errorMessage ?? 'No users found.'}
                  </td>
                </tr>
              )}
              {isLoading && (
                <tr>
                  <td className="px-4 py-6 text-sm text-muted-foreground" colSpan={5}>
                    Loading users...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            Page {page} of {totalPages} · {total} users
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

export default Users;
