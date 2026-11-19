import adapter from '@sveltejs/adapter-node';

const envTrustedOrigins = (process.env.TRUSTED_ORIGINS || '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

const trustedOrigins = [
  'http://localhost:8510',
  'http://127.0.0.1:8510',
  ...envTrustedOrigins,
];

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter(),
    csrf: {
      trustedOrigins,
    },
    csp: {
      mode: 'auto',
      directives: {
        'default-src': ['self'],
        'script-src': ['self'],
        'style-src': ['self', 'unsafe-inline'],
        'img-src': ['self', 'data:', 'blob:'],
        'font-src': ['self'],
        'connect-src': ['self'],
        'frame-ancestors': ['none'],
        'base-uri': ['self'],
        'form-action': ['self'],
      },
    },
    // Check for a newly deployed build every 5 minutes; the UpdateBanner shows when one is found.
    version: {
      pollInterval: 300000
    },
    alias: {
      $lib: 'src/lib'
    }
  }
};

export default config;
