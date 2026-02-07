import { cn } from '@/lib/utils';
import type { Severity, RunStatus, IssueStatus } from '@/data/mockData';

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
}

const severityStyles: Record<Severity, string> = {
  P0: 'bg-severity-p0/15 text-severity-p0 border-severity-p0/30',
  P1: 'bg-severity-p1/15 text-severity-p1 border-severity-p1/30',
  P2: 'bg-severity-p2/15 text-severity-p2 border-severity-p2/30',
  P3: 'bg-severity-p3/15 text-severity-p3 border-severity-p3/30',
};

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border', severityStyles[severity], className)}>
      {severity}
    </span>
  );
}

interface RunStatusBadgeProps {
  status: RunStatus;
  className?: string;
}

const runStatusStyles: Record<RunStatus, string> = {
  Running: 'bg-status-running/15 text-status-running border-status-running/30',
  Completed: 'bg-status-success/15 text-status-success border-status-success/30',
  Failed: 'bg-severity-p0/15 text-severity-p0 border-severity-p0/30',
};

export function RunStatusBadge({ status, className }: RunStatusBadgeProps) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border', runStatusStyles[status], className)}>
      {status === 'Running' && <span className="w-1.5 h-1.5 rounded-full bg-status-running animate-pulse-dot" />}
      {status}
    </span>
  );
}

interface IssueStatusBadgeProps {
  status: IssueStatus;
  className?: string;
}

const issueStatusStyles: Record<IssueStatus, string> = {
  New: 'bg-primary/10 text-primary border-primary/20',
  Investigating: 'bg-severity-p1/15 text-severity-p1 border-severity-p1/30',
  Assigned: 'bg-severity-p2/15 text-severity-p2 border-severity-p2/30',
  Resolved: 'bg-status-success/15 text-status-success border-status-success/30',
};

export function IssueStatusBadge({ status, className }: IssueStatusBadgeProps) {
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border', issueStatusStyles[status], className)}>
      {status}
    </span>
  );
}

interface CategoryBadgeProps {
  category: string;
  className?: string;
}

export function CategoryBadge({ category, className }: CategoryBadgeProps) {
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-secondary text-secondary-foreground border border-border', className)}>
      {category}
    </span>
  );
}
