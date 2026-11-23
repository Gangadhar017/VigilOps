import { get, post } from './client';

// The browser only ever talks to the VigilOps backend. The Gemini API key is
// held by the backend and is never present in this application.
export const vigilaiApi = {
  status: () => get('/api/assistant/status'),
  chat: (message, history = []) => post('/api/assistant/chat', { message, history }),
};
