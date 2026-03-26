import type { FileEntry, Project, AIModel, DataSourceSearchRecord } from '../types';
import { readDataSourceAuthorization } from './dataSourceAuth';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  // Only set Content-Type for requests with a body
  if (options?.body) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...options,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${text}`);
  }
  if (!text) return undefined as T; // 204 No Content or empty body
  return JSON.parse(text) as T;
}

export async function fetchFileTree(projectId: string): Promise<FileEntry[]> {
  return request<FileEntry[]>(`/files/${projectId}/tree`);
}

export async function fetchFileContent(projectId: string, path: string): Promise<string> {
  const data = await request<{ path: string; content: string }>(
    `/files/${projectId}/content?path=${encodeURIComponent(path)}`
  );
  return data.content;
}

export async function saveFileContent(projectId: string, path: string, content: string): Promise<void> {
  await request(`/files/${projectId}/content`, {
    method: 'PUT',
    body: JSON.stringify({ path, content }),
  });
}

export type SearchHit = { line: number; column: number; preview: string };
export type SearchResult = { path: string; uri?: string; hits: SearchHit[] };

export async function searchFiles(
  sessionId: string,
  query: string,
  opts?: { caseSensitive?: boolean; maxResults?: number; maxHitsPerFile?: number }
): Promise<SearchResult[]> {
  const data = await request<{ query: string; results: SearchResult[] }>(`/files/${sessionId}/search`, {
    method: 'POST',
    body: JSON.stringify({
      query,
      case_sensitive: opts?.caseSensitive ?? false,
      max_results: opts?.maxResults ?? 2000,
      max_hits_per_file: opts?.maxHitsPerFile ?? 200,
    }),
  });
  return data.results;
}

export async function fetchProjects(): Promise<Project[]> {
  return request<Project[]>('/projects');
}

export async function createProject(name: string): Promise<Project> {
  return request<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

export async function deleteProject(id: string): Promise<void> {
  await request(`/projects/${id}`, { method: 'DELETE' });
}

export async function renameProject(projectId: string, name: string): Promise<void> {
  await request(`/projects/${projectId}/name`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  });
}

export async function updateProjectModel(projectId: string, model: string): Promise<void> {
  await request(`/projects/${projectId}/model`, {
    method: 'PATCH',
    body: JSON.stringify({ model }),
  });
}

export async function fetchPreviewPort(projectId: string): Promise<number> {
  const data = await request<{ port: number }>(`/preview/${projectId}/port`);
  return data.port;
}

export async function fetchChatHistory(projectId: string): Promise<{ id: string; role: string; content: string; created_at: string }[]> {
  return request(`/chat/${projectId}/history`);
}

export async function fetchAgentEvents(projectId: string): Promise<Record<string, unknown>[]> {
  return request(`/chat/${projectId}/events`);
}

export async function fetchModels(): Promise<AIModel[]> {
  return request<AIModel[]>('/models');
}

export async function fetchDefaultModel(): Promise<string> {
  const data = await request<{ model: string }>('/models/default');
  return data.model;
}

export async function searchDataSources(queryOrId: string): Promise<DataSourceSearchRecord[]> {
  const headers: Record<string, string> = {};
  const auth = readDataSourceAuthorization();
  if (auth) headers.Authorization = auth;
  const res = await fetch(`${BASE}/data-source/search/${encodeURIComponent(queryOrId)}`, { headers });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${text}`);
  }
  if (!text) return [] as DataSourceSearchRecord[];
  return JSON.parse(text) as DataSourceSearchRecord[];
}

export function downloadZip(projectId: string): void {
  window.open(`${BASE}/export/${projectId}/zip`, '_blank');
}

export function downloadSingleHtml(projectId: string): void {
  window.open(`${BASE}/export/${projectId}/html`, '_blank');
}

export async function publishToS3(projectId: string): Promise<{ url: string; project_name: string }> {
  return request<{ url: string; project_name: string }>(`/export/${projectId}/publish`, {
    method: 'POST',
  });
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    await request<Project[]>('/projects');
    return true;
  } catch (error) {
    console.error('Backend health check failed:', error);
    return false;
  }
}
