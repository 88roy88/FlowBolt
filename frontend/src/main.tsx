import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { AuthGate } from './auth';
import App from './App';
import './App.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate>
      <App />
    </AuthGate>
  </StrictMode>,
);
