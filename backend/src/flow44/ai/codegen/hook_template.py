"""Deterministic React hook generator for data source fetching."""

from __future__ import annotations


def generate_data_source_hook(
    data_source_id: str,
    sanitized_name: str,
    types_import_path: str,
) -> str:
    """Generate a React hook file that fetches from a data source endpoint.

    Args:
        data_source_id: The FLAPI data source ID.
        sanitized_name: PascalCase name (e.g. "WeatherForecastApi").
        types_import_path: Relative import path for types
                           (e.g. "../types/dataSourceWeatherForecastApi").

    Returns:
        Complete TypeScript file content.
    """
    hook_name = f"useDataSource{sanitized_name}"
    response_type = f"{sanitized_name}Response"

    # TODO: move to jinja
    return f"""\
import {{ useState, useEffect, useCallback }} from 'react';
import {{ API_BASE }} from '../config';
import {{ credentialsStore, authSession }} from '../auth';
import type {{ {response_type} }} from '{types_import_path}';

async function fetchWithAuth(url: string, body?: unknown): Promise<Response> {{
  const token = credentialsStore.getValidToken();
  const options: RequestInit = {{
    method: 'POST',
    headers: {{
      'Content-Type': 'application/json',
      ...(token ? {{ Authorization: token }} : {{}}),
    }},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  }};
  const res = await fetch(url, options);
  if (res.status === 401) {{
    await authSession.refreshAfter401();
    const retryToken = credentialsStore.getValidToken();
    const retry = await fetch(url, {{
      ...options,
      headers: {{
        'Content-Type': 'application/json',
        ...(retryToken ? {{ Authorization: retryToken }} : {{}}),
      }},
    }});
    if (!retry.ok) throw new Error(`Request failed: ${{retry.status}}`);
    return retry;
  }}
  if (!res.ok) throw new Error(`Request failed: ${{res.status}}`);
  return res;
}}

export function {hook_name}() {{
  const [data, setData] = useState<{response_type} | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {{
    setIsLoading(true);
    setError(null);
    try {{
      const res = await fetchWithAuth(`${{API_BASE}}/api/data-source/{data_source_id}/run`);
      const json: {response_type} = await res.json();
      setData(json);
    }} catch (err) {{
      setError(err instanceof Error ? err.message : 'Unknown error');
    }} finally {{
      setIsLoading(false);
    }}
  }}, []);

  useEffect(() => {{ fetchData(); }}, [fetchData]);

  return {{ data, isLoading, error, refetch: fetchData }};
}}
"""
