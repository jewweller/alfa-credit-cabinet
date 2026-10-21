import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router';
import { ApplicationPage } from './pages/client/ApplicationPage';
import { ComingSoonPage } from './pages/client/ComingSoonPage';
import { HomePage } from './pages/client/HomePage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<ComingSoonPage code="C1" />} />
          <Route path="/products" element={<ComingSoonPage code="C3" />} />
          <Route path="/applications/:id/edit" element={<ComingSoonPage code="C4" />} />
          <Route path="/applications/:id" element={<ApplicationPage />} />
          <Route path="/applications/:id/signing" element={<ComingSoonPage code="C6" />} />
          <Route path="/applications/:id/result" element={<ComingSoonPage code="C7" />} />
          <Route path="/feed" element={<ComingSoonPage code="C8" />} />
          <Route path="*" element={<ComingSoonPage code="404" />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
