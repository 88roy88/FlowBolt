export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: Action[];
  timestamp: number;
}

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
}

export interface AIModel {
  id: string;
  name: string;
  provider: string;
}

export type WSMessage =
  | { type: 'message'; content: string; model?: string }
  | { type: 'text'; content: string }
  | { type: 'file'; path: string; content: string }
  | { type: 'shell_output'; command: string; output: string }
  | { type: 'action_complete' }
  | { type: 'error'; message: string };
