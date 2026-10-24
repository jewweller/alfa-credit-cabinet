import { FEED, type FeedFilter } from '../../i18n/ru';
import { EmptyState, ErrorBanner, FeedPanel, SkeletonLine } from '../../ui';
import { FeedEntry } from './FeedEntry';
import type { useFeed } from './useFeed';

/** Полная лента (C8) с выбранным фильтром. */
export function FeedList({ feed, filter, now }: { feed: ReturnType<typeof useFeed>; filter: FeedFilter; now: number }) {
  const P = FEED.page;
  const items = feed.data?.items;

  return (
    <FeedPanel title={P.panel[filter]} caption={P.caption[filter]}>
      {feed.isPending && Array.from({ length: 5 }, (_, i) => <SkeletonLine key={i} />)}

      {feed.isError && (
        <ErrorBanner message={FEED.loadError} retryLabel={FEED.retry} onRetry={() => feed.refetch()} retrying={feed.isFetching} />
      )}

      {items?.length === 0 && <EmptyState title={P.empty[filter]} compact />}

      {items?.map((item, i) => <FeedEntry key={item.id} item={item} index={Math.min(i, 8)} now={now} withMarkButton />)}
    </FeedPanel>
  );
}
