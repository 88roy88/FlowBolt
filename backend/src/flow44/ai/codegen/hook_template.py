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

    return f"""\
import {{ useState, useEffect, useCallback }} from 'react';
import {{ API_BASE }} from '../config';
import {{ credentialsStore, authSession }} from '../auth';
import type {{ {response_type} }} from '{types_import_path}';

async function fetchWithAuth(url: string): Promise<Response> {{
  const token = await authSession.ensureFreshToken();
  const res = await fetch(url, {{
    headers: token ? {{ Authorization: token }} : undefined,
  }});
  if (res.status === 401) {{
    await authSession.refreshAfter401();
    const retryToken = credentialsStore.getValidToken();
    const retry = await fetch(url, {{
      headers: retryToken ? {{ Authorization: retryToken }} : undefined,
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
