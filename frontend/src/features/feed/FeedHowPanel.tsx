import type { FeedRanking } from '../../api/types';
import { FEED } from '../../i18n/ru';
import { KeyValueList, MetaNote, Panel } from '../../ui';

/** «Как подбираются новости»: веса правил и версия подбора — чтобы порядок не был чёрным ящиком. */
export function FeedHowPanel({ ranking }: { ranking: FeedRanking | undefined }) {
  const H = FEED.how;
  return (
    <Panel eyebrow={H.eyebrow} title={H.title}>
      <p>{H.text}</p>
      <KeyValueList items={H.weights} />
      <p>{H.filters}</p>
      {ranking?.method === 'ml' && <p>{H.ml}</p>}
      <p>{H.noBki}</p>
      {ranking && <MetaNote>{H.version(ranking.method, ranking.model_version)}</MetaNote>}
    </Panel>
  );
}
