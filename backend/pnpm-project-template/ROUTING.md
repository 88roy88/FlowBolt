# Routing in Generated Apps

This template may be served under nested URLs during preview and publish.

When the work plan sets `"uses_routing": true`, the generated app needs client-side routing. That flag is a plan capability only: the backend installs `react-router-dom` and does not own your route definitions. Single-page apps keep `"uses_routing": false` and render without React Router.

Do not hardcode preview or publish paths in React code.

Vite receives the public base path from the backend through `VITE_BASE_PATH`.
The Vite config applies it as `base`.
Inside React code, use Vite's standard `import.meta.env.BASE_URL`.

For apps without routing:

- Do not install `react-router-dom`.
- Do not add router wrappers.
- Render `<App />` directly.

For apps with routing:

- Install `react-router-dom`.
- Use `src/platform/routerBasename.ts`.
- Wrap routes with `BrowserRouter basename={getRouterBasename()}` or pass `basename: getRouterBasename()` to `createBrowserRouter`.

Example BrowserRouter usage:

```tsx
import { BrowserRouter } from 'react-router-dom';
import { getRouterBasename } from './platform/routerBasename';

<BrowserRouter basename={getRouterBasename()}>
  <App />
</BrowserRouter>
```

Example createBrowserRouter usage:

```tsx
const router = createBrowserRouter(routes, {
  basename: getRouterBasename(),
});
```

Do not remove files under `src/platform/` unless intentionally changing platform support.

Do not add `<base href>` to `index.html`.
Do not hardcode `/api/preview/...` or `/api/export/...` in React code.
Vite `base` owns asset paths.
React Router `basename` owns client routes.
