package com.poetry.config;

import com.poetry.interceptor.CallbackInterceptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 注册回调拦截器，仅限制 /api/v1/poetry/callback 路径
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Autowired
    private CallbackInterceptor callbackInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(callbackInterceptor)
                .addPathPatterns("/api/v1/poetry/callback");
    }
}
