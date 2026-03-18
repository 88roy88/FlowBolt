export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: Action[];
  timestamp: number;
  package?: { id: number; name: string } | null;
  // Agent card data (persisted in chat history)
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
  | { type: 'package_fetched'; packageId: string; packageName: string; dataSchema: string; relevantFields?: string };

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
  | 'fetching_package'
  | 'designing'
  | 'planning'
  | 'awaiting_approval'
  | 'executing'
  | 'fixing'
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

export type WSMessage =
  | { type: 'message'; content: string; model?: string; packageId?: number }
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
  | { type: 'package_fetched'; package_id: string; package_name: string; data_schema: string; relevant_fields?: string }
  | { type: 'package_error'; message: string };
