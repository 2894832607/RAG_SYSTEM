import axios from 'axios';
export const gateway = axios.create({
    baseURL: '/api/v1',
    timeout: 120000
});
export function login(username, password) {
    return gateway.post('/auth/login', { username, password });
}
export function register(username, password, nickname) {
    return gateway.post('/auth/register', { username, password, nickname });
}
export function submitPoemTask(poemText) {
    return gateway.post('/poetry/visualize', { poemText });
}
export function fetchTaskStatus(taskId) {
    return gateway.get(`/poetry/task/${taskId}`);
}
export function fetchCallbackPayload(taskId) {
    return gateway.get(`/poetry/callback/${taskId}`);
}
//# sourceMappingURL=api.js.map