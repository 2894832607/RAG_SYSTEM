package com.example.poetryvisualization.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 全局跨域配置 — 允许前端 Vue dev-server 跨域访问后端 API
 */
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    private final AppSecurityProperties appSecurityProperties;
    private final AuthTokenInterceptor authTokenInterceptor;

    public CorsConfig(AppSecurityProperties appSecurityProperties, AuthTokenInterceptor authTokenInterceptor) {
        this.appSecurityProperties = appSecurityProperties;
        this.authTokenInterceptor = authTokenInterceptor;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        String[] origins = appSecurityProperties.getCors().getAllowedOrigins().toArray(new String[0]);
        registry.addMapping("/**")
                .allowedOrigins(origins)
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(authTokenInterceptor).addPathPatterns("/api/v1/**");
    }
}
