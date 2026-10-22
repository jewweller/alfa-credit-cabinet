import { toCardView } from '../../features/applications/cardView';
import { formatToday } from '../../features/format';
import { groupForHome } from '../../features/applications/homeGroups';
import { useApplications } from '../../features/applications/useApplications';
import { HomeFeed } from '../../features/feed/HomeFeed';
import { useProductMap } from '../../features/products/useProducts';
import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { firstName, useMe } from '../../features/session/useMe';
import { useNow } from '../../features/useNow';
import { HOME } from '../../i18n/ru';
import {
  ApplicationCard,
  AppShell,
  ButtonLink,
  Collapsible,
  EmptyState,
  ErrorBanner,
  Hero,
  Section,
  SkeletonCard,
  SplitLayout,
  type HeroStat,
} from '../../ui';
import type { ApplicationSummary } from '../../api/types';

const pad = (n: number) => String(n).padStart(2, '0');

/** C2 — главная клиента. */
export function HomePage() {
  const now = useNow();
  const { data: me } = useMe();
  const apps = useApplications();
  const products = useProductMap();

  const groups = apps.isSuccess ? groupForHome(apps.data) : null;
  const hasApps = (apps.data?.length ?? 0) > 0;

  const cards = (items: ApplicationSummary[]) =>
    items.map((app, i) => <ApplicationCard key={app.id} {...toCardView(app, now, products, i)} />);

  const stats: HeroStat[] | null | undefined = groups
    ? hasApps
      ? [
          { value: pad(groups.action.length), label: HOME.stats.action, accent: groups.action.length > 0 },
          { value: pad(groups.bank.length), label: HOME.stats.bank },
          { value: pad(groups.done.length), label: HOME.stats.done },
        ]
      : undefined
    : apps.isPending
      ? null
      : undefined;

  const hero = (
    <Hero
      eyebrow={formatToday(now)}
      title={HOME.greeting(new Date(now).getHours(), firstName(me?.full_name))}
      subtitle={groups ? HOME.summary(groups.action.length, groups.bank.length) : apps.isPending ? null : undefined}
      stats={stats}
      action={
        hasApps && (
          <ButtonLink to={ROUTES.products} variant="night" arrow>
            {HOME.pickCredit}
          </ButtonLink>
        )
      }
    />
  );

  const renderMain = () => {
    if (apps.isPending) {
      return (
        <>
          <SkeletonCard label={HOME.loading} />
          <SkeletonCard label={HOME.loading} index={1} />
        </>
      );
    }

    if (apps.isError) {
      return (
        <ErrorBanner
          message={HOME.loadError}
          detail={apps.error.message}
          retryLabel={HOME.retry}
          onRetry={() => apps.refetch()}
          retrying={apps.isFetching}
        />
      );
    }

    if (!groups || !hasApps) {
      return (
        <EmptyState
          eyebrow={HOME.empty.eyebrow}
          title={HOME.empty.title}
          text={HOME.empty.text}
          action={
            <ButtonLink to={ROUTES.products} size="lg" arrow>
              {HOME.pickCredit}
            </ButtonLink>
          }
        />
      );
    }

    return (
      <>
        {groups.action.length > 0 && (
          <Section title={HOME.blocks.action} count={groups.action.length} highlighted>
            {cards(groups.action)}
          </Section>
        )}

        {groups.bank.length > 0 && (
          <Section title={HOME.blocks.bank} count={groups.bank.length} live={HOME.liveLabel}>
            {cards(groups.bank)}
          </Section>
        )}

        {groups.done.length > 0 && (
          <Collapsible title={HOME.blocks.done} count={groups.done.length}>
            {cards(groups.done)}
          </Collapsible>
        )}
      </>
    );
  };

  return (
    <AppShell header={<ClientHeader />} hero={hero}>
      <SplitLayout main={renderMain()} aside={<HomeFeed now={now} />} />
    </AppShell>
  );
}
