export type Severity = 'P0' | 'P1' | 'P2' | 'P3';
export type RunStatus = 'Running' | 'Completed' | 'Failed';
export type RunResult = 'No issues' | 'Issue found' | 'Crash';
export type IssueStatus = 'New' | 'Investigating' | 'Assigned' | 'Resolved';
export type Category = 'Backend' | 'Frontend' | 'UX Copy' | 'Performance' | 'Integration';
export type Device = 'iPhone SE' | 'iPhone 14' | 'Pixel 7';
export type Network = 'WiFi' | '4G' | 'Slow 3G' | 'High latency';
export type Locale = 'EN' | 'AR' | 'HI';

export interface AgentStep {
  time: string;
  action: string;
  status: 'success' | 'warning' | 'error' | 'info';
}

export interface Run {
  id: string;
  startedAt: string;
  duration: string;
  device: Device;
  network: Network;
  locale: Locale;
  status: RunStatus;
  result: RunResult;
  severity?: Severity;
  issueId?: string;
  steps: AgentStep[];
}

export interface Issue {
  id: string;
  title: string;
  severity: Severity;
  category: Category;
  status: IssueStatus;
  device: Device;
  network: Network;
  locale: Locale;
  timeStuck: string;
  diagnosis: string;
  suggestedOwner: string;
  detectedAt: string;
  runId: string;
  steps: AgentStep[];
}

export interface EvidenceItem {
  id: string;
  type: 'screenshot' | 'clip';
  runId: string;
  issueId?: string;
  device: Device;
  timestamp: string;
  step: string;
  color: string;
}

export interface KpiData {
  runsToday: number;
  issuesDetected: number;
  avgTimeToDetect: number;
  criticalBlockers: number;
}

export const kpiData: KpiData = {
  runsToday: 24,
  issuesDetected: 7,
  avgTimeToDetect: 8.3,
  criticalBlockers: 3,
};

export const agentLogEntries: AgentStep[] = [
  { time: '0.0s', action: 'Opened signup page', status: 'success' },
  { time: '1.2s', action: 'Detected fields: Name, Email, Password', status: 'info' },
  { time: '2.8s', action: 'Typed name: Alex Johnson', status: 'success' },
  { time: '4.1s', action: 'Typed email: alex@test.com', status: 'success' },
  { time: '5.5s', action: 'Typed password', status: 'success' },
  { time: '6.2s', action: 'Tapped Continue', status: 'success' },
  { time: '6.8s', action: 'Spinner detected', status: 'warning' },
  { time: '18.8s', action: 'Stuck for 12 seconds', status: 'error' },
  { time: '19.0s', action: 'Timeout threshold exceeded', status: 'error' },
  { time: '19.2s', action: 'Capturing evidence', status: 'info' },
];

const sharedSteps: AgentStep[] = [
  { time: '0.0s', action: 'Opened signup page', status: 'success' },
  { time: '1.5s', action: 'Detected form fields', status: 'info' },
  { time: '3.0s', action: 'Filled form data', status: 'success' },
  { time: '4.5s', action: 'Tapped Continue', status: 'success' },
  { time: '5.0s', action: 'Waiting for response', status: 'warning' },
];

export const runs: Run[] = [
  { id: 'RUN-001', startedAt: '2026-02-06T09:00:00Z', duration: '19s', device: 'iPhone 14', network: 'WiFi', locale: 'EN', status: 'Completed', result: 'Issue found', severity: 'P0', issueId: 'ISS-001', steps: agentLogEntries },
  { id: 'RUN-002', startedAt: '2026-02-06T09:15:00Z', duration: '8s', device: 'Pixel 7', network: '4G', locale: 'EN', status: 'Completed', result: 'No issues', steps: sharedSteps },
  { id: 'RUN-003', startedAt: '2026-02-06T09:30:00Z', duration: '22s', device: 'iPhone SE', network: 'Slow 3G', locale: 'AR', status: 'Completed', result: 'Issue found', severity: 'P1', issueId: 'ISS-002', steps: [...sharedSteps, { time: '12.0s', action: 'Layout broken in RTL mode', status: 'error' }] },
  { id: 'RUN-004', startedAt: '2026-02-06T09:45:00Z', duration: '5s', device: 'iPhone 14', network: 'WiFi', locale: 'EN', status: 'Failed', result: 'Crash', severity: 'P0', issueId: 'ISS-003', steps: [...sharedSteps.slice(0, 3), { time: '4.0s', action: 'App crashed on submit', status: 'error' }] },
  { id: 'RUN-005', startedAt: '2026-02-06T10:00:00Z', duration: '7s', device: 'Pixel 7', network: 'High latency', locale: 'HI', status: 'Completed', result: 'No issues', steps: sharedSteps },
  { id: 'RUN-006', startedAt: '2026-02-06T10:15:00Z', duration: '15s', device: 'iPhone SE', network: '4G', locale: 'EN', status: 'Completed', result: 'Issue found', severity: 'P2', issueId: 'ISS-004', steps: [...sharedSteps, { time: '10.0s', action: 'Password hint text unclear', status: 'warning' }] },
  { id: 'RUN-007', startedAt: '2026-02-06T10:30:00Z', duration: '—', device: 'iPhone 14', network: 'WiFi', locale: 'EN', status: 'Running', result: 'No issues', steps: agentLogEntries.slice(0, 5) },
  { id: 'RUN-008', startedAt: '2026-02-06T10:45:00Z', duration: '9s', device: 'Pixel 7', network: 'Slow 3G', locale: 'EN', status: 'Completed', result: 'No issues', steps: sharedSteps },
  { id: 'RUN-009', startedAt: '2026-02-05T14:00:00Z', duration: '18s', device: 'iPhone 14', network: '4G', locale: 'AR', status: 'Completed', result: 'Issue found', severity: 'P1', issueId: 'ISS-005', steps: [...sharedSteps, { time: '14.0s', action: 'OTP field not visible', status: 'error' }] },
  { id: 'RUN-010', startedAt: '2026-02-05T15:00:00Z', duration: '6s', device: 'iPhone SE', network: 'WiFi', locale: 'HI', status: 'Completed', result: 'No issues', steps: sharedSteps },
  { id: 'RUN-011', startedAt: '2026-02-05T16:00:00Z', duration: '25s', device: 'Pixel 7', network: 'High latency', locale: 'EN', status: 'Completed', result: 'Issue found', severity: 'P3', issueId: 'ISS-006', steps: [...sharedSteps, { time: '20.0s', action: 'Slow API response detected', status: 'warning' }] },
  { id: 'RUN-012', startedAt: '2026-02-05T17:00:00Z', duration: '4s', device: 'iPhone 14', network: 'WiFi', locale: 'EN', status: 'Failed', result: 'Crash', severity: 'P0', issueId: 'ISS-007', steps: [...sharedSteps.slice(0, 2), { time: '3.0s', action: 'Network error: 502 Bad Gateway', status: 'error' }] },
];

export const issues: Issue[] = [
  { id: 'ISS-001', title: 'Signup spinner hangs indefinitely on submit', severity: 'P0', category: 'Backend', status: 'New', device: 'iPhone 14', network: 'WiFi', locale: 'EN', timeStuck: '12s', diagnosis: 'The signup API endpoint /api/v1/register returns a 504 Gateway Timeout after 12 seconds. The backend auth service appears to be failing silently, causing the frontend spinner to hang with no error feedback to the user.', suggestedOwner: 'Backend Team', detectedAt: '2026-02-06T09:00:19Z', runId: 'RUN-001', steps: agentLogEntries },
  { id: 'ISS-002', title: 'RTL layout breaks form alignment in Arabic locale', severity: 'P1', category: 'Frontend', status: 'New', device: 'iPhone SE', network: 'Slow 3G', locale: 'AR', timeStuck: '—', diagnosis: 'Form input labels and fields are misaligned when the locale is set to Arabic (RTL). The CSS flexbox direction is not correctly flipped, causing overlapping text and unusable form inputs.', suggestedOwner: 'Frontend Team', detectedAt: '2026-02-06T09:30:22Z', runId: 'RUN-003', steps: sharedSteps },
  { id: 'ISS-003', title: 'App crashes on form submit with null pointer', severity: 'P0', category: 'Frontend', status: 'Investigating', device: 'iPhone 14', network: 'WiFi', locale: 'EN', timeStuck: '—', diagnosis: 'The application crashes with an unhandled TypeError when the user submits the signup form. A null reference is accessed in the form validation handler, likely due to an optional field not being initialized.', suggestedOwner: 'Frontend Team', detectedAt: '2026-02-06T09:45:05Z', runId: 'RUN-004', steps: sharedSteps },
  { id: 'ISS-004', title: 'Password requirements hint text is truncated on small screens', severity: 'P2', category: 'UX Copy', status: 'Investigating', device: 'iPhone SE', network: '4G', locale: 'EN', timeStuck: '—', diagnosis: 'The password hint text "Must contain at least 8 characters, one uppercase..." is cut off on iPhone SE viewport. The container does not allow text wrapping, hiding critical requirements from users.', suggestedOwner: 'Design Team', detectedAt: '2026-02-06T10:15:15Z', runId: 'RUN-006', steps: sharedSteps },
  { id: 'ISS-005', title: 'OTP input field not visible below the fold on mobile', severity: 'P1', category: 'Frontend', status: 'Assigned', device: 'iPhone 14', network: '4G', locale: 'AR', timeStuck: '8s', diagnosis: 'After submitting the signup form, the OTP verification field renders below the visible viewport. The page does not auto-scroll to the input, leaving users confused about the next step.', suggestedOwner: 'Frontend Team', detectedAt: '2026-02-05T14:00:18Z', runId: 'RUN-009', steps: sharedSteps },
  { id: 'ISS-006', title: 'Slow API response causes perceived freeze on submit', severity: 'P3', category: 'Performance', status: 'Assigned', device: 'Pixel 7', network: 'High latency', locale: 'EN', timeStuck: '15s', diagnosis: 'Under high-latency network conditions, the signup API takes 15+ seconds to respond. No loading indicator or timeout message is shown, making users believe the app has frozen.', suggestedOwner: 'Backend Team', detectedAt: '2026-02-05T16:00:25Z', runId: 'RUN-011', steps: sharedSteps },
  { id: 'ISS-007', title: 'Backend 502 error on signup endpoint', severity: 'P0', category: 'Backend', status: 'Resolved', device: 'iPhone 14', network: 'WiFi', locale: 'EN', timeStuck: '—', diagnosis: 'The signup API returned a 502 Bad Gateway error. Root cause was a misconfigured load balancer that dropped connections to the auth service. Resolved by infrastructure team.', suggestedOwner: 'Infrastructure Team', detectedAt: '2026-02-05T17:00:04Z', runId: 'RUN-012', steps: sharedSteps },
  { id: 'ISS-008', title: 'Email validation accepts invalid TLD formats', severity: 'P2', category: 'Integration', status: 'Resolved', device: 'Pixel 7', network: 'WiFi', locale: 'EN', timeStuck: '—', diagnosis: 'The email validation regex on the frontend accepts emails with invalid TLDs like "user@test.c". This can lead to failed delivery and poor user experience when the backend rejects the email later.', suggestedOwner: 'Frontend Team', detectedAt: '2026-02-05T12:00:00Z', runId: 'RUN-002', steps: sharedSteps },
];

export const evidenceItems: EvidenceItem[] = [
  { id: 'EV-001', type: 'screenshot', runId: 'RUN-001', issueId: 'ISS-001', device: 'iPhone 14', timestamp: '2026-02-06T09:00:18Z', step: 'Spinner stuck on submit', color: 'from-severity-p0/20 to-severity-p0/5' },
  { id: 'EV-002', type: 'clip', runId: 'RUN-001', issueId: 'ISS-001', device: 'iPhone 14', timestamp: '2026-02-06T09:00:19Z', step: '10s recording of spinner hang', color: 'from-severity-p0/20 to-severity-p0/5' },
  { id: 'EV-003', type: 'screenshot', runId: 'RUN-003', issueId: 'ISS-002', device: 'iPhone SE', timestamp: '2026-02-06T09:30:12Z', step: 'RTL layout broken', color: 'from-severity-p1/20 to-severity-p1/5' },
  { id: 'EV-004', type: 'screenshot', runId: 'RUN-004', issueId: 'ISS-003', device: 'iPhone 14', timestamp: '2026-02-06T09:45:04Z', step: 'Crash on submit', color: 'from-severity-p0/20 to-severity-p0/5' },
  { id: 'EV-005', type: 'clip', runId: 'RUN-004', issueId: 'ISS-003', device: 'iPhone 14', timestamp: '2026-02-06T09:45:05Z', step: '10s recording before crash', color: 'from-severity-p0/20 to-severity-p0/5' },
  { id: 'EV-006', type: 'screenshot', runId: 'RUN-006', issueId: 'ISS-004', device: 'iPhone SE', timestamp: '2026-02-06T10:15:10Z', step: 'Truncated password hint', color: 'from-severity-p2/20 to-severity-p2/5' },
  { id: 'EV-007', type: 'screenshot', runId: 'RUN-009', issueId: 'ISS-005', device: 'iPhone 14', timestamp: '2026-02-05T14:00:14Z', step: 'OTP field below fold', color: 'from-severity-p1/20 to-severity-p1/5' },
  { id: 'EV-008', type: 'clip', runId: 'RUN-009', issueId: 'ISS-005', device: 'iPhone 14', timestamp: '2026-02-05T14:00:18Z', step: '10s recording of missing OTP', color: 'from-severity-p1/20 to-severity-p1/5' },
  { id: 'EV-009', type: 'screenshot', runId: 'RUN-011', issueId: 'ISS-006', device: 'Pixel 7', timestamp: '2026-02-05T16:00:20Z', step: 'Frozen UI during slow response', color: 'from-severity-p3/20 to-severity-p3/5' },
  { id: 'EV-010', type: 'screenshot', runId: 'RUN-012', issueId: 'ISS-007', device: 'iPhone 14', timestamp: '2026-02-05T17:00:03Z', step: '502 error screen', color: 'from-severity-p0/20 to-severity-p0/5' },
  { id: 'EV-011', type: 'screenshot', runId: 'RUN-002', device: 'Pixel 7', timestamp: '2026-02-06T09:15:06Z', step: 'Successful signup flow', color: 'from-status-success/20 to-status-success/5' },
  { id: 'EV-012', type: 'clip', runId: 'RUN-005', device: 'Pixel 7', timestamp: '2026-02-06T10:00:07Z', step: 'Full signup flow recording', color: 'from-status-success/20 to-status-success/5' },
];
