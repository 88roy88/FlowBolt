# Routing in Generated Apps

This template may be served under nested URLs during preview and publish.

When the work plan sets `"uses_routing": true`, the generated app needs client-side routing. That flag is a plan capability only: the backend installs `react-router-dom` and does not own your route definitions. Single-page apps keep `"uses_routing": false` and render without React Router.

Do not hardcode preview or publish paths in React code.

## Platform contract (two layers)

| Layer | Source | AI must |
|-------|--------|---------|
| **Vite `base`** | Backend sets `VITE_BASE_PATH` → `vite.config.ts` uses `const base = env.VITE_BASE_PATH \|\| '/'` | **Never edit** `vite.config.ts`, `index.html`, or env files |
| **Router `basename`** | `getRouterBasename()` in `src/platform/routerBasename.ts` reads `import.meta.env.BASE_URL` | Wrap app in `<BrowserRouter basename={getRouterBasename()}>` in **`App.tsx` only** |

**Never remove** the `base` option from `vite.config.ts`.  
**Never** hardcode `base: '/'` or preview/export paths in Vite config.  
**Never** add `<base href>` to `index.html`.  
**Never** manually `define` `import.meta.env.BASE_URL` in Vite — Vite derives it from `base`.

For apps without routing:

- Do not install `react-router-dom`.
- Do not add router wrappers.
- Render `<App />` directly from `main.tsx`.

For apps with routing:

- Install `react-router-dom` (backend may do this when `uses_routing` is true).
- Use `src/platform/routerBasename.ts` — do not rewrite it.
- Wire **`App.tsx`** with `BrowserRouter basename={getRouterBasename()}` (or `createBrowserRouter` with the same `basename`).
- Do **not** put `BrowserRouter` in `main.tsx`.

Example `App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { getRouterBasename } from './platform/routerBasename';

export default function App() {
  return (
    <BrowserRouter basename={getRouterBasename()}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/cart" element={<CartPage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

Example `createBrowserRouter`:

```tsx
const router = createBrowserRouter(routes, {
  basename: getRouterBasename(),
});
```

## Internal navigation (critical)

Apps run under a nested public base during preview and publish. Plain `<a href="/…">` navigates to the **host root**, not your app — it breaks routing and leaves the preview.

For **every in-app route** (`/`, `/cart`, `/category/foo`, 404 “back home”, navbar links, buttons that change pages):

- Use `Link` or `NavLink` from `react-router-dom` with app-relative `to` paths: `<Link to="/">Home</Link>`.
- Use `useNavigate()` for programmatic navigation: `navigate('/cart')`.
- Never use `<a href="/…">`, `<a href={pathname}>`, or `window.location` / `location.assign` for in-app pages.

External URLs (another domain, `mailto:`, `tel:`) may use `<a href="https://…">` with a full absolute URL.

Do not remove or rewrite files under `src/platform/` unless intentionally changing platform support.

Do not hardcode `/api/preview/...` or `/api/export/...` in React code.

Vite `base` owns asset paths.  
React Router `basename` owns client routes.
