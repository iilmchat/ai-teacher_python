// Runtime-конфигурация frontend (S35-002).
// В production файл перезаписывается entrypoint'ом контейнера из ENV:
//   SENTRY_DSN, SENTRY_ENVIRONMENT, APP_RELEASE, SENTRY_TRACES_SAMPLE_RATE.
// Пустой sentryDsn = Sentry выключен (no-op).
window.__APP_CONFIG__ = {
  sentryDsn: '',
  sentryEnvironment: 'development',
  release: '',
  sentryTracesSampleRate: 0,
};
