import { useState, type FormEvent } from 'react';
import { Navigate, useSearchParams } from 'react-router';
import { ApiError, readToken } from '../../api/client';
import { ROUTES } from '../../features/routes';
import { SurfaceSwitch } from '../../features/session/SurfaceSwitch';
import { useLogin } from '../../features/session/useLogin';
import { HEADER, LOGIN } from '../../i18n/ru';
import { AccountPicker, AppShell, AuthLayout, Button, Form, InlineAlert, Panel, PublicHeader, TextField } from '../../ui';

/** Подсказку с тестовыми учётками прячем только явно: VITE_DEMO_MODE=false (план, экран C1). */
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false';

/** C1 / B1 — вход. Роль определяется учёткой. */
export function LoginPage() {
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [missing, setMissing] = useState(false);
  const login = useLogin(params.get('next'));

  if (readToken() !== null && login.isIdle) return <Navigate to={ROUTES.home} replace />;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim() || !password) {
      setMissing(true);
      return;
    }
    setMissing(false);
    login.mutate({ email: email.trim(), password });
  };

  const error = missing
    ? LOGIN.required
    : login.error
      ? login.error instanceof ApiError && login.error.status === 401
        ? LOGIN.wrong
        : LOGIN.failed
      : null;

  return (
    <AppShell header={<PublicHeader productName={HEADER.product} homeHref={ROUTES.login} tools={<SurfaceSwitch />} />}>
      <AuthLayout eyebrow={LOGIN.eyebrow} title={LOGIN.title} subtitle={LOGIN.subtitle} points={LOGIN.points}>
        <Panel tone="highlight" eyebrow={LOGIN.formEyebrow} title={LOGIN.formTitle}>
          <Form layout="contents" onSubmit={onSubmit}>
            <TextField
              label={LOGIN.email}
              type="email"
              autoComplete="username"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={missing && !email.trim() ? LOGIN.required : null}
            />
            <TextField
              label={LOGIN.password}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={missing && !password ? LOGIN.required : null}
            />
            {error && !missing && <InlineAlert>{error}</InlineAlert>}
            <Button type="submit" size="lg" arrow disabled={login.isPending}>
              {login.isPending ? LOGIN.submitting : LOGIN.submit}
            </Button>
          </Form>
        </Panel>

        {DEMO_MODE && (
          <Panel eyebrow={LOGIN.demo.eyebrow} title={LOGIN.demo.title} index={1}>
            <AccountPicker
              accounts={LOGIN.demo.accounts.map((a) => ({ email: a.email, name: a.name, note: a.scenario }))}
              selected={email}
              onPick={(picked) => {
                setEmail(picked);
                setPassword(LOGIN.demo.password);
                setMissing(false);
                login.reset();
              }}
            />
            <InlineAlert tone="info">{LOGIN.demo.hint}</InlineAlert>
          </Panel>
        )}
      </AuthLayout>
    </AppShell>
  );
}
