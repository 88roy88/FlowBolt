import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://pro-jolly-monster.ngrok-free.app',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://pro-jolly-monster.ngrok-free.app',
        ws: true,
      },
    },
  },
});
