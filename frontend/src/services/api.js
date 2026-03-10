import axios from 'axios';
export const gateway = axios.create({
    baseURL: '/api/v1',
    timeout: 120000
});
let authToken = '';
export function setAuthToken(token) {
    authToken = token;
}
gateway.interceptors.request.use((config) => {
    if (authToken) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${authToken}`;
    }
    return config;
});
gateway.interceptors.response.use((response) => response, (error) => {
    if (error?.response?.status === 401) {
        localStorage.removeItem('poetry_auth_token');
        localStorage.removeItem('poetry_auth_user');
        if (window.location.pathname !== '/login') {
            const redirect = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.href = `/login?redirect=${redirect}`;
        }
    }
    return Promise.reject(error);
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
/** 查询当前用户历史生成任务（走 Backend JWT 认证） */
export function fetchHistory(page = 1, pageSize = 20) {
    return gateway.get('/poetry/history', { params: { page, pageSize } });
}
/** 创建对话会话（经由 Backend 代理到 AI Service） */
export function createChatSession() {
    return gateway.post('/poetry/chat/session');
}
//# sourceMappingURL=api.js.map