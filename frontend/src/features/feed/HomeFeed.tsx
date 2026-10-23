import { FEED, HOME } from '../../i18n/ru';
import { EmptyState, ErrorBanner, FeedItem, FeedPanel, SkeletonLine } from '../../ui';
import { timeAgo } from '../format';
import { ROUTES } from '../routes';
import { HOME_FEED_LIMIT, useFeed } from './useFeed';

/** Лента на главной. Падает отдельно от заявок и не ломает экран. */
export function HomeFeed({ now }: { now: number }) {
  const feed = useFeed(HOME_FEED_LIMIT);

  return (
    <FeedPanel title={FEED.title} caption={FEED.caption} footer={{ label: FEED.all, to: ROUTES.feed }}>
      {feed.isPending && Array.from({ length: 3 }, (_, i) => <SkeletonLine key={i} />)}

      {feed.isError && (
        <ErrorBanner
          message={FEED.loadError}
          retryLabel={HOME.retry}
          onRetry={() => feed.refetch()}
          retrying={feed.isFetching}
        />
      )}

      {feed.isSuccess && feed.data.length === 0 && <EmptyState title={FEED.empty} compact />}

      {feed.isSuccess &&
        feed.data.map((item, i) => (
          <FeedItem
            key={item.id}
            index={i}
            kind={item.kind}
            kindLabel={FEED.kind[item.kind]}
            title={item.title}
            body={item.body}
            time={timeAgo(item.created_at, now)}
            unread={!item.read}
            unreadLabel={FEED.unread}
            reason={item.reason ? { label: FEED.reasonLabel, text: item.reason } : null}
            to={item.application_id ? ROUTES.application(item.application_id) : null}
          />
        ))}
    </FeedPanel>
  );
}
