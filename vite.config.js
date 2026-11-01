import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiAuthToken = process.env.API_AUTH_TOKEN || env.API_AUTH_TOKEN;
  const apiBackendUrl =
    process.env.API_BACKEND_URL || env.API_BACKEND_URL || 'http://127.0.0.1:5001';

  if (command === 'serve' && !apiAuthToken) {
    console.warn(
      'API_AUTH_TOKEN is not set. Health checks can run, but protected API requests will be unauthorized.',
    );
  }

  return {
    server: {
      proxy: {
        '/api': {
          target: apiBackendUrl,
          changeOrigin: true,
          headers: apiAuthToken ? { Authorization: `Bearer ${apiAuthToken}` } : {},
        },
      },
    },
  };
});
