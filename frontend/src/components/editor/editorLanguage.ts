export function getEditorLanguageForPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();

  const langMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    json: 'json',
    html: 'html',
    css: 'css',
    scss: 'scss',
    less: 'less',
    md: 'markdown',
    py: 'python',
    yaml: 'yaml',
    yml: 'yaml',
    toml: 'toml',
    sh: 'shell',
    bash: 'shell',
    svg: 'xml',
  };

  return langMap[ext ?? ''] ?? 'plaintext';
}
