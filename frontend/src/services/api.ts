import axios from 'axios';

export const gateway = axios.create({
  baseURL: '/api/v1',
  timeout: 120000
});

let authToken = '';

export function setAuthToken(token: string) {
  authToken = token;
}

gateway.interceptors.request.use((config) => {
  if (authToken) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${authToken}`;
  }
  return config;
});

gateway.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('poetry_auth_token');
      localStorage.removeItem('poetry_auth_user');
      if (window.location.pathname !== '/login') {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/login?redirect=${redirect}`;
      }
    }
    return Promise.reject(error);
  }
);

export function login(username: string, password: string) {
  return gateway.post('/auth/login', { username, password });
}

export function register(username: string, password: string, nickname: string) {
  return gateway.post('/auth/register', { username, password, nickname });
}

export function submitPoemTask(poemText: string) {
  return gateway.post('/poetry/visualize', { poemText });
}

export function fetchTaskStatus(taskId: string) {
  return gateway.get(`/poetry/task/${taskId}`);
}

export function fetchCallbackPayload(taskId: string) {
  return gateway.get(`/poetry/callback/${taskId}`);
}
