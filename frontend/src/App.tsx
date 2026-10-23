import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router';
import { ApiError, clearToken } from './api/client';
import type { UserRole } from './api/types';
import { ROUTES } from './features/routes';
import { RequireAuth } from './features/session/RequireAuth';
import { LoginPage } from './pages/auth/LoginPage';
import { ApplicationEditPage } from './pages/client/ApplicationEditPage';
import { ApplicationPage } from './pages/client/ApplicationPage';
import { ComingSoonPage } from './pages/client/ComingSoonPage';
import { HomePage } from './pages/client/HomePage';
import { ProductsPage } from './pages/client/ProductsPage';
import { BankApplicationPage } from './pages/bank/BankApplicationPage';
import { QueuePage } from './pages/bank/QueuePage';
import { ResultPage } from './pages/client/ResultPage';
import { SigningPage } from './pages/client/SigningPage';

/** Токен истёк или недействителен — на вход, с возвратом на текущий экран. */
function onUnauthorized(error: Error) {
  if (error instanceof ApiError && error.status === 401 && window.location.pathname !== ROUTES.login) {
    clearToken();
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.assign(`${ROUTES.login}?next=${next}`);
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onUnauthorized }),
  mutationCache: new MutationCache({ onError: onUnauthorized }),
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const CLIENT: UserRole[] = ['client'];
const BANK: UserRole[] = ['underwriter', 'admin'];

const client = (page: ReactNode) => <RequireAuth roles={CLIENT}>{page}</RequireAuth>;
const bank = (page: ReactNode) => <RequireAuth roles={BANK}>{page}</RequireAuth>;

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path={ROUTES.login} element={<LoginPage />} />
          <Route path="/" element={client(<HomePage />)} />
          <Route path="/products" element={client(<ProductsPage />)} />
          <Route path="/applications/:id/edit" element={client(<ApplicationEditPage />)} />
          <Route path="/applications/:id" element={client(<ApplicationPage />)} />
          <Route path="/applications/:id/signing" element={client(<SigningPage />)} />
          <Route path="/applications/:id/result" element={client(<ResultPage />)} />
          <Route path="/feed" element={client(<ComingSoonPage code="C8" />)} />
          <Route path={ROUTES.bank} element={bank(<QueuePage />)} />
          <Route path="/bank/applications/:id" element={bank(<BankApplicationPage />)} />
          <Route path="*" element={client(<ComingSoonPage code="404" />)} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
