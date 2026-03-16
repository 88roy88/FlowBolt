"""Dev entry point: cd backend && uv run python run.py"""

import uvicorn

if __name__ == "__main__":
    print(f"Starting backend server...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["data/**", "*.db"],
    )
