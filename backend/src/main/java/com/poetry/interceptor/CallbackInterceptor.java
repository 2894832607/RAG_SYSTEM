package com.poetry.interceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * Spec: specs/features/interface-communication.spec.md §3.3
 * 校验来自 AI Service 的回调请求是否携带正确的 X-Callback-Token
 */
@Component
public class CallbackInterceptor implements HandlerInterceptor {

    @Value("${poetry.callback-token}")
    private String expectedToken;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String providedToken = request.getHeader("X-Callback-Token");

        if (expectedToken == null || expectedToken.isEmpty()) {
            // 如果未配置 token，则默认允许（仅用于核心开发阶段，生产环境应报警）
            return true;
        }

        if (expectedToken.equals(providedToken)) {
            return true;
        }

        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.getWriter().write("{\"code\": 401, \"message\": \"Invalid callback token\"}");
        return false;
    }
}
