import { useState } from 'react';
import { FeedHowPanel } from '../../features/feed/FeedHowPanel';
import { FeedList } from '../../features/feed/FeedList';
import { useFeed } from '../../features/feed/useFeed';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { useNow } from '../../features/useNow';
import { FEED, type FeedFilter } from '../../i18n/ru';
import { AppShell, BackLink, FilterBar, FilterChips, Hero, SplitLayout } from '../../ui';

const FILTERS: FeedFilter[] = ['all', 'event', 'news'];
// На полной ленте новостей больше, чем на главной.
const NEWS_LIMIT = 20;

/** C8. Полная лента: события по заявкам и новости по профилю, с фильтром и объяснением подбора. */
export function FeedPage() {
  const P = FEED.page;
  const now = useNow();
  const [filter, setFilter] = useState<FeedFilter>('all');
  const all = useFeed({ newsLimit: NEWS_LIMIT });
  const filtered = useFeed({ kind: filter === 'all' ? null : filter, newsLimit: NEWS_LIMIT });
  const feed = filter === 'all' ? all : filtered;

  const items = all.data?.items;
  const stats = items
    ? [
        { label: P.stats.unread, value: String(items.filter((i) => i.kind === 'event' && !i.read).length), accent: true },
        { label: P.stats.news, value: String(items.filter((i) => i.kind === 'news').length) },
      ]
    : null;

  return (
    <AppShell
      header={<ClientHeader />}
      hero={
        <Hero
          top={<BackLink to={ROUTES.home} label={P.back} />}
          eyebrow={P.eyebrow}
          title={P.title}
          subtitle={P.subtitle}
          stats={stats}
          action={
            <FilterBar>
              <FilterChips label={P.filter} value={filter} onChange={setFilter} options={FILTERS.map((f) => ({ value: f, label: P.filters[f] }))} />
            </FilterBar>
          }
        />
      }
    >
      <SplitLayout main={<FeedList feed={feed} filter={filter} now={now} />} aside={<FeedHowPanel ranking={all.data?.ranking} />} />
    </AppShell>
  );
}
