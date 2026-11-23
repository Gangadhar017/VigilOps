import { get, post } from './client';

export const authApi = {
  login: (email, password) => post('/api/auth/login', { email, password }),
  logout: () => post('/api/auth/logout'),
  me: () => get('/api/auth/me'),
  changePassword: (current_password, new_password) =>
    post('/api/auth/change-password', { current_password, new_password }),
};
