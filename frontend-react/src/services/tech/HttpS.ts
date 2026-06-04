import axios from 'axios';

import EnvS from './EnvS';

// ============================================================================
// Private — protocol details (auth, base URL, SSE wire format)
// ============================================================================

const authHeaders = (): Record<string, string> => {
  const key = EnvS.apiKey();
  return key ? { 'X-API-Key': key } : {};
};

const jsonHeaders = (): Record<string, string> => ({
  'Content-Type': 'application/json',
  ...authHeaders(),
});

const url = (path: string): string => `${EnvS.apiUrl()}${path}`;

// ============================================================================
// Public service API
// ============================================================================

export interface StreamCallbacks {
  onData: (data: string) => void;
  onDone: () => void;
  onError: (error: Error) => void;
}

const get = async <T>(path: string): Promise<T> => {
  const { data } = await axios.get<T>(url(path), { headers: authHeaders() });
  return data;
};

const post = async <T>(
  path: string,
  body?: unknown,
  params?: Record<string, string>,
): Promise<T> => {
  const { data } = await axios.post<T>(url(path), body ?? null, {
    params,
    headers: authHeaders(),
  });
  return data;
};

const postForm = async <T>(path: string, form: FormData): Promise<T> => {
  const { data } = await axios.post<T>(url(path), form, { headers: authHeaders() });
  return data;
};

const del = async (path: string): Promise<void> => {
  await axios.delete(url(path), { headers: authHeaders() });
};

const stream = (path: string, body: unknown, callbacks: StreamCallbacks): AbortController => {
  const controller = new AbortController();

  void (async () => {
    try {
      const res = await fetch(url(path), {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Stream request failed: ${res.status.toString()}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') {
            callbacks.onDone();
            return;
          }
          callbacks.onData(data);
        }
      }

      callbacks.onDone();
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      callbacks.onError(e instanceof Error ? e : new Error('Stream error'));
    }
  })();

  return controller;
};

const HttpS = { get, post, postForm, del, stream };
export default HttpS;
