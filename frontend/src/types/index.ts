export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: Action[];
  timestamp: number;
  dataSources?: { id: number; name: string }[];
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
  | { type: 'plan_overview'; overview: PlanOverview }
  | { type: 'task_progress'; tasks: ExecutionTask[] }
  | { type: 'project_summary'; summary: ProjectSummary }
  | { type: 'error_fix_request'; errorMessage: string; errorFile?: string; errorLine?: number; errorStack?: string }
  | { type: 'fix_progress'; steps: FixStep[] }
  | { type: 'data_sources_fetched'; dataSources: { dataSourceId: string; dataSourceName: string; dataSchema: string; relevantFields?: string }[] }

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

export interface DataSourceSearchRecord {
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
  | 'fetching_data_sources'
  | 'designing'
  | 'planning'
  | 'awaiting_approval'
  | 'executing'
  | 'fixing'
  | 'exploring'
  | 'complete';

/** SCREAMING_SNAKE_CASE form of a string union (e.g. `idle` → `IDLE`). */
export type CapitalChars<T extends string> = Uppercase<T>;

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
  | { type: 'auth'; dataSourceAuthorization?: string }
  | { type: 'message'; content: string; model?: string; dataSourceIds?: number[] }
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
  | { type: 'plan_response'; action: 'accept' | 'modify'; feedback?: string }
  | { type: 'project_summary'; summary: ProjectSummary }
  | { type: 'fix_step'; step: 'discover' | 'generate' | 'write' | 'validate' | 'retry'; status: 'running' | 'completed' | 'failed'; message: string }
  | { type: 'fix_error'; error_message: string; error_file?: string; error_line?: number; error_stack?: string; model?: string }
  | { type: 'data_sources_fetched'; data_sources: { data_source_id: string; data_source_name: string; data_schema: string; relevant_fields?: string }[] }
  | { type: 'data_source_error'; message: string }

  | { type: 'followup_step'; tool: string; args: Record<string, string>; status: string; result_preview?: string; iteration: number }
  | { type: 'followup_diffs'; diffs: FileDiff[] }
  | { type: 'user_message'; content: string; data_sources?: { id: number; name: string }[]; error_fix_request?: { errorMessage: string; errorFile?: string; errorLine?: number; errorStack?: string } }
  | { type: 'plan_accepted'; overview: PlanOverview };
