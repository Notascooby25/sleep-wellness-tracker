import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const buildDate = new Date().toLocaleDateString('en-GB', {
  day: 'numeric', month: 'short', year: 'numeric'
});

export default defineConfig({
  plugins: [sveltekit()],
  define: {
    __BUILD_DATE__: JSON.stringify(buildDate)
  }
});
