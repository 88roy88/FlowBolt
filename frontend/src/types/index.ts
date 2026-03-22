export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: Action[];
  timestamp: number;
  cases?: { id: number; name: string }[];
  agentCard?: AgentCard;
}

export interface ProjectSummary {
  summary: string;
  tech_stack: string[];
  features: string[];
  file_overview: Record<string, string>;
}

export type AgentCard =
  | { type: 'design_complete'; architecture: boolean; ux: boolean }
  | { type: 'plan_overview'; overview: PlanOverview; accepted: boolean }
  | { type: 'task_progress'; tasks: ExecutionTask[] }
  | { type: 'project_summary'; summary: ProjectSummary }
  | { type: 'error_fix_request'; errorMessage: string; errorFile?: string; errorLine?: number; errorStack?: string }
  | { type: 'fix_progress'; steps: FixStep[] }
  | { type: 'cases_fetched'; cases: { packageId: string; packageName: string; dataSchema: string; relevantFields?: string }[] }

  | { type: 'followup_progress'; steps: FollowUpStep[]; answer?: string; filesChanged?: string[]; diffs?: FileDiff[] };

export interface Action {
  type: 'file' | 'shell';
  path?: string;
  content?: string;
  command?: string;
  output?: string;
}

export interface FileEntry {
  name: string;
  path: string;
  is_directory: boolean;
  children?: FileEntry[];
}

export interface Project {
  id: string;
  name: string;
  session_id: string;
  created_at: string;
  summary?: string;
  selected_model?: string;
  published_url?: string;
}

export interface AIModel {
  id: string;
  name: string;
  provider: string;
}

export interface PackageSearchRecord {
  Id: number;
  Name: string;
  Purpose?: string;
  Description?: string;
  UserName?: string;
  TimedPackageCount?: number;
  Tags?: string;
  Subjects?: string;
  [key: string]: unknown;
}

// Agent types
export type AgentPhase =
  | 'idle'
  | 'classifying'
  | 'fetching_cases'
  | 'designing'
  | 'planning'
  | 'awaiting_approval'
  | 'executing'
  | 'fixing'
  | 'exploring'
  | 'complete';

// User-facing plan overview (shown during approval)
export interface PlanFeature {
  title: string;
  description: string;
}

export interface PlanDecision {
  id: string;
  title: string;
  chosen: string;
  alternatives: string[];
}

export interface PlanOverview {
  summary: string;
  features: PlanFeature[];
  decisions: PlanDecision[];
}

// Execution tasks (shown during build progress, title-only)
export interface ExecutionTask {
  id: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export interface FixStep {
  id: string;
  step: 'discover' | 'generate' | 'write' | 'validate' | 'retry';
  status: 'running' | 'completed' | 'failed';
  message: string;
}

export interface FileDiff {
  path: string;
  diff: string;
}

export interface FollowUpStep {
  id: string;
  tool: 'grep' | 'glob' | 'read_file' | 'write_file' | 'edit_file';
  args: Record<string, string>;
  status: 'running' | 'completed' | 'failed';
  resultPreview?: string;
  iteration: number;
}

export type WSMessage =
  | { type: 'message'; content: string; model?: string; caseIds?: number[] }
  | { type: 'text'; content: string }
  | { type: 'file'; path: string; content: string }
  | { type: 'shell_output'; command: string; output: string }
  | { type: 'action_complete' }
  | { type: 'error'; message: string }
  | { type: 'phase'; phase: AgentPhase }
  | { type: 'design_progress'; stream: 'architecture' | 'ux'; content: string }
  | { type: 'plan_overview'; overview: PlanOverview }
  | { type: 'task_list'; tasks: ExecutionTask[] }
  | { type: 'task_update'; taskId: string; status: 'running' | 'completed' | 'failed'; file?: string }
  | { type: 'plan_response'; action: 'accept' | 'reject' | 'modify'; feedback?: string }
  | { type: 'project_summary'; summary: ProjectSummary }
  | { type: 'fix_step'; step: 'discover' | 'generate' | 'write' | 'validate' | 'retry'; status: 'running' | 'completed' | 'failed'; message: string }
  | { type: 'fix_error'; error_message: string; error_file?: string; error_line?: number; error_stack?: string; model?: string }
  | { type: 'cases_fetched'; cases: { package_id: string; package_name: string; data_schema: string; relevant_fields?: string }[] }
  | { type: 'case_error'; message: string }

  | { type: 'followup_step'; tool: string; args: Record<string, string>; status: string; result_preview?: string; iteration: number }
  | { type: 'followup_diffs'; diffs: FileDiff[] }
  | { type: 'user_message'; content: string; cases?: { id: number; name: string }[]; error_fix_request?: { errorMessage: string; errorFile?: string; errorLine?: number; errorStack?: string } }
  | { type: 'plan_accepted'; overview: PlanOverview }
  | { type: 'plan_rejected'; overview: PlanOverview };
