import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const packageJson = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf8')) as {
  version?: string;
};
const appVersion = packageJson.version || '0.0.0';

const buildDate = new Date().toLocaleDateString('en-GB', {
  day: 'numeric', month: 'short', year: 'numeric'
});

export default defineConfig({
  plugins: [sveltekit()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __BUILD_DATE__: JSON.stringify(buildDate)
  }
});
