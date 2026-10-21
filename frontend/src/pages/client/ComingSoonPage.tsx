import { ROUTES } from '../../features/routes';
import { ClientHeader } from '../../features/session/ClientHeader';
import { COMING_SOON } from '../../i18n/ru';
import { AppShell, ButtonLink, EmptyState } from '../../ui';

/** Временная страница для экранов, которые ещё не свёрстаны. */
export function ComingSoonPage({ code }: { code: string }) {
  return (
    <AppShell header={<ClientHeader />}>
      <EmptyState
        title={COMING_SOON.title(code)}
        text={COMING_SOON.text}
        action={
          <ButtonLink to={ROUTES.home} variant="secondary">
            {COMING_SOON.back}
          </ButtonLink>
        }
      />
    </AppShell>
  );
}
