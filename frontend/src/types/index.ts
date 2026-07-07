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
  | { type: 'fix_progress'; steps: FixStep[]; diffs?: FileDiff[] }
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

export const ProjectRoles = {
  owner: 'owner',
  viewer: 'viewer',
  editor: 'editor',
  publisher: 'publisher',
  maintainer: 'maintainer',
  admin: 'admin',
} as const;

export type ProjectRole = (typeof ProjectRoles)[keyof typeof ProjectRoles];
export type AssignableRole = 'viewer' | 'editor' | 'publisher' | 'maintainer';

export const WRITE_ROLES: ReadonlySet<ProjectRole> = new Set([
  ProjectRoles.owner, ProjectRoles.editor, ProjectRoles.maintainer, ProjectRoles.admin,
]);
export const PUBLISH_ROLES: ReadonlySet<ProjectRole> = new Set([
  ProjectRoles.owner, ProjectRoles.publisher, ProjectRoles.maintainer, ProjectRoles.admin,
]);
export const MANAGE_ROLES: ReadonlySet<ProjectRole> = new Set([
  ProjectRoles.owner, ProjectRoles.maintainer, ProjectRoles.admin,
]);
export const DELETE_ROLES: ReadonlySet<ProjectRole> = new Set([
  ProjectRoles.owner, ProjectRoles.admin,
]);

export interface Project {
  id: string;
  name: string;
  created_at: string;
  user_id?: string;
  summary?: string;
  selected_model?: string;
  published_url?: string;
  role?: ProjectRole;
}

export interface ProjectMember {
  user_id: string;
  role: AssignableRole;
  created_at: string;
  invited_by: string;
}

export interface UserStatus {
  user_id: string;
  is_admin: boolean;
  is_platform_user: boolean;
}

export interface AIModel {
  id: string;
  name: string;
  provider: string;
}

export interface DataSourceSearchResult {
  id: number;
  name: string;
  description: string | null;
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

export type AgentPhaseConstMap = { readonly [K in AgentPhase]: K };

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
  is_new?: boolean;
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
  | { type: 'file_diffs'; diffs: FileDiff[] }
  | { type: 'user_message'; content: string; data_sources?: { id: number; name: string }[]; error_fix_request?: { errorMessage: string; errorFile?: string; errorLine?: number; errorStack?: string } }
  | { type: 'plan_accepted'; overview: PlanOverview };
