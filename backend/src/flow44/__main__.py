"""Entry point for running the server."""

import uvicorn


def main_dev() -> None:
    """Run the server with auto-reload for development."""
    uvicorn.run(
        "flow44.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src/flow44"],
        log_level="info",
    )


def main() -> None:
    uvicorn.run(
        "flow44.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
