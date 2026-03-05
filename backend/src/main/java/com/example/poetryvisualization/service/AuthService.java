package com.example.poetryvisualization.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.poetryvisualization.dto.LoginRequest;
import com.example.poetryvisualization.dto.RegisterRequest;
import com.example.poetryvisualization.entity.User;
import com.example.poetryvisualization.mapper.UserMapper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.util.HashMap;
import java.util.Map;

@Service
public class AuthService {

    private final UserMapper userMapper;
    private final TokenService tokenService;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    public AuthService(UserMapper userMapper, TokenService tokenService) {
        this.userMapper = userMapper;
        this.tokenService = tokenService;
    }

    public Map<String, Object> register(RegisterRequest request) {
        String username = request.getUsername().trim();
        String nickname = request.getNickname().trim();

        User exists = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, username));
        if (exists != null) {
            throw new IllegalArgumentException("用户名已存在");
        }

        User user = new User();
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setNickname(StringUtils.hasText(nickname) ? nickname : username);
        user.setAvatar("");
        user.setStatus(1);
        userMapper.insert(user);

        Map<String, Object> userInfo = new HashMap<>();
        userInfo.put("id", user.getId());
        userInfo.put("username", user.getUsername());
        userInfo.put("nickname", user.getNickname());

        Map<String, Object> data = new HashMap<>();
        data.put("token", tokenService.issueToken(user.getId()));
        data.put("user", userInfo);
        return data;
    }

    public Map<String, Object> login(LoginRequest request) {
        String username = request.getUsername().trim();

        User user = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, username));

        if (user == null || user.getStatus() == null || user.getStatus() != 1) {
            throw new IllegalArgumentException("账号不存在或已禁用");
        }
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new IllegalArgumentException("用户名或密码错误");
        }

        Map<String, Object> userInfo = new HashMap<>();
        userInfo.put("id", user.getId());
        userInfo.put("username", user.getUsername());
        userInfo.put("nickname", user.getNickname());

        Map<String, Object> data = new HashMap<>();
        data.put("token", tokenService.issueToken(user.getId()));
        data.put("user", userInfo);
        return data;
    }
}
