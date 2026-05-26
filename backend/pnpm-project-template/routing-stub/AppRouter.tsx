import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { getRouterBasename } from '../utils/routerBasename';

export function AppRouter({ children }: { children: React.ReactNode }): React.ReactElement {
  return <BrowserRouter basename={getRouterBasename()}>{children}</BrowserRouter>;
}
