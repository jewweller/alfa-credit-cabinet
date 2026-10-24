import type { FeedItem as FeedItemData } from '../../api/types';
import { FEED } from '../../i18n/ru';
import { Button, FeedItem } from '../../ui';
import { timeAgo } from '../format';
import { ROUTES } from '../routes';
import { useMarkFeedRead } from './useFeed';

/**
 * Запись ленты. Событие гаснет, когда клиент переходит к заявке;
 * withMarkButton — ещё и кнопка «Отметить прочитанным» (полная лента).
 */
export function FeedEntry({ item, index, now, withMarkButton = false }: { item: FeedItemData; index: number; now: number; withMarkButton?: boolean }) {
  const markRead = useMarkFeedRead();
  const unread = item.kind === 'event' && !item.read;
  const mark = () => unread && markRead.mutate(item.id);

  return (
    <FeedItem
      index={index}
      kind={item.kind}
      kindLabel={item.application_number ? `${FEED.kind.event} №${item.application_number}` : FEED.kind[item.kind]}
      title={item.title}
      body={item.body}
      time={timeAgo(item.created_at, now)}
      unread={unread}
      unreadLabel={FEED.unread}
      reasons={item.reasons.length ? { label: FEED.reasonLabel, items: item.reasons.map((r) => r.text) } : null}
      to={item.application_id ? ROUTES.application(item.application_id) : null}
      onOpen={mark}
      action={
        withMarkButton && unread ? (
          <Button variant="ghost" onClick={mark} disabled={markRead.isPending}>
            {FEED.markRead}
          </Button>
        ) : null
      }
    />
  );
}
