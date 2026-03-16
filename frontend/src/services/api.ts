import type { FileEntry, Project } from '../types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchFileTree(sessionId: string): Promise<FileEntry[]> {
  return request<FileEntry[]>(`/sessions/${sessionId}/files`);
}

export async function fetchFileContent(sessionId: string, path: string): Promise<string> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/files/content?path=${encodeURIComponent(path)}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch file content: ${res.status}`);
  }
  return res.text();
}

export async function saveFileContent(sessionId: string, path: string, content: string): Promise<void> {
  await request(`/sessions/${sessionId}/files/content`, {
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
