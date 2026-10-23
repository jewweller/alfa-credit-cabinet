import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import type { Product } from '../../api/types';

/** Каталог меняется редко — грузим один раз за сессию. */
export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: ({ signal }) => apiGet<Product[]>('/products', signal),
    staleTime: Infinity,
  });
}

/** id продукта → продукт. Пока каталог грузится, вернёт пустую карту. */
export function useProductMap(): Map<string, Product> {
  const { data } = useProducts();
  return new Map((data ?? []).map((p) => [p.id, p]));
}
