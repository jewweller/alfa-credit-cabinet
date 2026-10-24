import { FEED } from '../../i18n/ru';
import { EmptyState, ErrorBanner, FeedPanel, SkeletonLine } from '../../ui';
import { ROUTES } from '../routes';
import { FeedEntry } from './FeedEntry';
import { HOME_FEED_LIMIT, useFeed } from './useFeed';

/** Лента на главной. Падает отдельно от заявок и не ломает экран. */
export function HomeFeed({ now }: { now: number }) {
  const feed = useFeed();
  const items = feed.data?.items.slice(0, HOME_FEED_LIMIT);

  return (
    <FeedPanel title={FEED.title} caption={FEED.caption} footer={{ label: FEED.all, to: ROUTES.feed }}>
      {feed.isPending && Array.from({ length: 3 }, (_, i) => <SkeletonLine key={i} />)}

      {feed.isError && (
        <ErrorBanner message={FEED.loadError} retryLabel={FEED.retry} onRetry={() => feed.refetch()} retrying={feed.isFetching} />
      )}

      {items?.length === 0 && <EmptyState title={FEED.empty} compact />}

      {items?.map((item, i) => <FeedEntry key={item.id} item={item} index={i} now={now} />)}
    </FeedPanel>
  );
}
