const envApiBase = String(import.meta.env.VITE_API_URL ?? '').trim();
const useRelativeApi = String(import.meta.env.VITE_USE_RELATIVE_API ?? '').trim() === '1';

if (!envApiBase && !useRelativeApi) {
  throw new Error('VITE_API_URL is not configured. Set API_PORT in the root .env file.');
}

export const API_BASE = envApiBase;
