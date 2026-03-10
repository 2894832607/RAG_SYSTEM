import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { login as loginApi, register as registerApi } from '../services/api';
import { setAuthToken } from '../services/api';
const AUTH_TOKEN_KEY = 'poetry_auth_token';
const AUTH_USER_KEY = 'poetry_auth_user';
export const useAuthStore = defineStore('auth', () => {
    const token = ref(localStorage.getItem(AUTH_TOKEN_KEY) || '');
    const user = ref(null);
    const userRaw = localStorage.getItem(AUTH_USER_KEY);
    if (userRaw) {
        try {
            user.value = JSON.parse(userRaw);
        }
        catch {
            localStorage.removeItem(AUTH_USER_KEY);
        }
    }
    if (token.value) {
        setAuthToken(token.value);
    }
    const isLoggedIn = computed(() => !!token.value && !!user.value);
    const persist = () => {
        if (token.value && user.value) {
            localStorage.setItem(AUTH_TOKEN_KEY, token.value);
            localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user.value));
            setAuthToken(token.value);
            return;
        }
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(AUTH_USER_KEY);
        setAuthToken('');
    };
    const login = async (username, password) => {
        const response = await loginApi(username, password);
        token.value = response.data?.data?.token || '';
        user.value = response.data?.data?.user || null;
        if (!token.value || !user.value) {
            throw new Error('登录响应缺少用户信息');
        }
        persist();
    };
    const register = async (username, password, nickname) => {
        const response = await registerApi(username, password, nickname);
        token.value = response.data?.data?.token || '';
        user.value = response.data?.data?.user || null;
        if (!token.value || !user.value) {
            throw new Error('注册响应缺少用户信息');
        }
        persist();
    };
    const logout = async () => {
        token.value = '';
        user.value = null;
        persist();
    };
    return { token, user, isLoggedIn, login, register, logout };
});
//# sourceMappingURL=auth.js.map