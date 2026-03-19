import type { FileEntry, Project, AIModel, PackageSearchRecord } from '../types';

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

export async function fetchFileTree(sessionId: string): Promise<FileEntry[]> {
  return request<FileEntry[]>(`/files/${sessionId}/tree`);
}

export async function fetchFileContent(sessionId: string, path: string): Promise<string> {
  const data = await request<{ path: string; content: string }>(
    `/files/${sessionId}/content?path=${encodeURIComponent(path)}`
  );
  return data.content;
}

export async function saveFileContent(sessionId: string, path: string, content: string): Promise<void> {
  await request(`/files/${sessionId}/content`, {
    method: 'PUT',
    body: JSON.stringify({ path, content }),
  });
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

export async function fetchPreviewPort(sessionId: string): Promise<number> {
  const data = await request<{ session_id: string; port: number }>(`/preview/${sessionId}/port`);
  return data.port;
}

export async function fetchChatHistory(sessionId: string): Promise<{ id: string; role: string; content: string; created_at: string }[]> {
  return request(`/chat/${sessionId}/history`);
}

export async function fetchModels(): Promise<AIModel[]> {
  return request<AIModel[]>('/models');
}

export async function fetchDefaultModel(): Promise<string> {
  const data = await request<{ model: string }>('/models/default');
  return data.model;
}

export async function searchPackages(queryOrId: string): Promise<PackageSearchRecord[]> {
  return request<PackageSearchRecord[]>(`/package/search/${encodeURIComponent(queryOrId)}`);
}

export function downloadZip(sessionId: string): void {
  window.open(`${BASE}/export/${sessionId}/zip`, '_blank');
}

export function downloadSingleHtml(sessionId: string): void {
  window.open(`${BASE}/export/${sessionId}/html`, '_blank');
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
