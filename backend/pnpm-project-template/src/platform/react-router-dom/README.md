# react-router-dom Platform Contract

Generated apps may use this folder only when `react-router-dom` is selected.

- Import `getRouterBasename` from `./platform/react-router-dom/routerBasename`.
- Wrap routes in `App.tsx` with `<BrowserRouter basename={getRouterBasename()}>`.
- Keep `BrowserRouter` out of `main.tsx`.
- Use `Link`, `NavLink`, or `useNavigate()` for internal routes; never use `<a href="/...">`.
- Do not edit `vite.config.ts`, `index.html`, env files, or files under `src/platform/`.
