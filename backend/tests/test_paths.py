from flow44.paths import preview_base_path, sandbox_path_env, shared_base_path, strip_public_base_prefix


def test_public_base_paths() -> None:
    assert preview_base_path("project-1") == "/api/preview/project-1/proxy/"
    assert shared_base_path("my-app") == "/shared/my-app/"


def test_sandbox_path_env_supports_old_and_new_vite_configs() -> None:
    env = sandbox_path_env(public_base="/shared/my-app/", api_base_url="https://api.example")
    assert env["VITE_BASE"] == "/shared/my-app/"
    assert env["VITE_BASE_PATH"] == "/shared/my-app/"
    assert env["VITE_API_BASE"] == "https://api.example"


def test_strip_public_base_prefix() -> None:
    assert strip_public_base_prefix("/shared/my-app/assets/main.js") == "assets/main.js"
    assert strip_public_base_prefix("/api/preview/project-1/proxy/assets/main.js") == "assets/main.js"
