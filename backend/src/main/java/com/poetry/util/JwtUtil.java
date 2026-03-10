package com.poetry.util;

import org.springframework.stereotype.Component;

import java.util.Date;

/**
 * 遗留 JWT 工具类（com.poetry 旧包）。
 * 主应用认证逻辑已迁移到 com.example.poetryvisualization.service.TokenService，
 * 本类仅保留以防旧代码引用，不再依赖 io.jsonwebtoken。
 */
@Component
public class JwtUtil {

    public String generateToken(String username) {
        // 已废弃：主应用使用 TokenService
        return "deprecated-" + username + "-" + System.currentTimeMillis();
    }

    public String getUsernameFromToken(String token) {
        return "";
    }

    public boolean validateToken(String token, String username) {
        return false;
    }
}
