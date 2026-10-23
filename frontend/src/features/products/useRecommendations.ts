import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiPost } from '../../api/client';
import type { ProductRecommendation, ProductRecommendRequest } from '../../api/types';

/** Подбор продукта (C3). Пока параметры неполные, запрос не уходит. */
export function useRecommendations(params: Partial<ProductRecommendRequest>) {
  const { purpose, amount, term_months } = params;
  const ready = Boolean(purpose && amount && Number(amount) > 0 && term_months && term_months > 0);
  return useQuery({
    queryKey: ['recommendations', purpose, amount, term_months],
    queryFn: ({ signal }) =>
      apiPost<ProductRecommendation[]>('/products/recommend', { body: { purpose, amount, term_months }, signal }),
    enabled: ready,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}
