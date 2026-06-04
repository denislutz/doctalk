const apiUrl = (): string => (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

const apiKey = (): string => (import.meta.env.VITE_API_KEY as string | undefined) ?? '';

const EnvS = { apiUrl, apiKey };
export default EnvS;
