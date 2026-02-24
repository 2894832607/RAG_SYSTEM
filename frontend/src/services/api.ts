import axios from 'axios';

const gateway = axios.create({
  baseURL: '/api/v1',
  timeout: 120000
});

export function submitPoemTask(poemText: string) {
  return gateway.post('/poetry/visualize', { poemText });
}

export function fetchTaskStatus(taskId: string) {
  return gateway.get(`/poetry/task/${taskId}`);
}

export function fetchCallbackPayload(taskId: string) {
  return gateway.get(`/poetry/callback/${taskId}`);
}
