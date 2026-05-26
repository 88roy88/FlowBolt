# Multi-page routing

Use this only when the app needs **multiple pages** or in-app navigation.

Flow44 installs `react-router-dom` and `src/router/AppRouter.tsx` automatically. Do **not** edit those files or `src/utils/routerBasename.ts`.

## What you edit

- `src/pages/*` — one default-export component per page
- `src/components/Navbar.tsx` — navigation with `Link` from `react-router-dom`
- `src/App.tsx` — wire routes (copy the pattern below)

## App.tsx pattern

```tsx
import { Routes, Route, Link } from 'react-router-dom';
import { AppRouter } from './router/AppRouter';
import HomePage from './pages/HomePage';
import AboutPage from './pages/AboutPage';
import Navbar from './components/Navbar';

export default function App() {
  return (
    <AppRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
      </Routes>
    </AppRouter>
  );
}
```

## Rules

1. Route paths are app-relative: `/`, `/about`, `/items/:id`
2. Navigation: `<Link to="/about">` from `react-router-dom` — never `<a href="/…">`
3. Programmatic nav: `useNavigate()` from `react-router-dom`
4. Do not edit `vite.config.ts`, `index.html`, or env files
