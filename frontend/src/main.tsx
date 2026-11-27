import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import { AuthGate } from './auth';
import App from './App';
import { WorkspaceGate } from './components/layout/WorkspaceGate';
import './App.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthGate>
        <WorkspaceGate>
          <App />
        </WorkspaceGate>
      </AuthGate>
    </QueryClientProvider>
  </StrictMode>,
);
