package com.example.poetryvisualization.service;

import com.example.poetryvisualization.config.AppSecurityProperties;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class TokenService {

    private final Map<String, TokenSession> sessions = new ConcurrentHashMap<>();
    private final AppSecurityProperties securityProperties;

    public TokenService(AppSecurityProperties securityProperties) {
        this.securityProperties = securityProperties;
    }

    public String issueToken(Long userId) {
        String token = UUID.randomUUID().toString().replace("-", "");
        Instant expireAt = Instant.now().plus(securityProperties.getTokenTtlMinutes(), ChronoUnit.MINUTES);
        sessions.put(token, new TokenSession(userId, expireAt));
        return token;
    }

    public Long verifyAndGetUserId(String token) {
        TokenSession session = sessions.get(token);
        if (session == null) {
            return null;
        }
        if (Instant.now().isAfter(session.expireAt())) {
            sessions.remove(token);
            return null;
        }
        return session.userId();
    }

    private record TokenSession(Long userId, Instant expireAt) {
    }
}
