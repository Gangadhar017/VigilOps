import { api, get } from './client';

// The browser only ever talks to the VigilOps backend. The Gemini API key is
// held by the backend and is never present in this application.
export const vigilaiApi = {
  status: () => get('/api/assistant/status'),
  // A generated answer can take longer than an ordinary request (the backend
  // allows the model 20 seconds, and the first answer after a restart also
  // loads the AI client), so this call gets a longer timeout than the default.
  chat: (message, history = []) =>
    api.post('/api/assistant/chat', { message, history }, { timeout: 60000 }).then((response) => response.data),
};
