import axios from 'axios';

const API_BASE_URL = 'http://localhost:8080/api/v1';

interface LoginCredentials {
    username: string;
    password: string;
}

interface RegisterPayload extends LoginCredentials {
    nickname: string;
}

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});


apiClient.interceptors.request.use(config => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, error => {
    return Promise.reject(error);
});

// Response Interceptor: Basic Error Handling
apiClient.interceptors.response.use(response => {
    return response.data; // Flatten ApiResponse structure
}, error => {
    if (error.response?.status === 401) {
        localStorage.removeItem('token');
        // window.location.href = '/login';
    }
    return Promise.reject(error);
});

export const apiService = {
    // Auth
    login: (credentials: LoginCredentials) => apiClient.post('/auth/login', credentials),
    register: (userData: RegisterPayload) => apiClient.post('/auth/register', userData),

    // Poetry
    visualize: (poemText: string) => apiClient.post('/poetry/visualize', { poemText }),
    getTask: (taskId: string) => apiClient.get(`/poetry/task/${taskId}`),
    getHistory: () => apiClient.get('/poetry/history'),
};
