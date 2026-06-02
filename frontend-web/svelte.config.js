import adapter from '@sveltejs/adapter-node';

const envTrustedOrigins = (process.env.TRUSTED_ORIGINS || '')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

const trustedOrigins = [
  'http://192.168.68.126:8510',
  'http://localhost:8510',
  'http://127.0.0.1:8510',
  'https://192.168.68.126:8510',
  ...envTrustedOrigins,
];

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter(),
    csrf: {
      trustedOrigins,
    },
    alias: {
      $lib: 'src/lib'
    }
  }
};

export default config;
