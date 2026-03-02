import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';
const routes = [
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/LoginView.vue'),
        meta: { title: '登录', public: true }
    },
    {
        path: '/',
        name: 'Generate',
        component: () => import('../views/GenerateView.vue'),
        meta: { title: '诗词可视化' }
    },
    {
        path: '/history',
        name: 'History',
        component: () => import('../views/HistoryView.vue'),
        meta: { title: '生成历史' }
    }
];
const router = createRouter({
    history: createWebHistory(),
    routes
});
router.beforeEach((to) => {
    const authStore = useAuthStore();
    if (!to.meta?.public && !authStore.isLoggedIn) {
        return '/login';
    }
    if (to.path === '/login' && authStore.isLoggedIn) {
        return '/';
    }
    document.title = `${to.meta.title || '诗词意境'} · Poetry RAG`;
});
export default router;
//# sourceMappingURL=index.js.map