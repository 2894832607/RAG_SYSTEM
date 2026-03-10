package com.poetry.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.poetry.dto.ApiResponse;
import com.poetry.entity.User;
import com.poetry.mapper.UserMapper;
import com.poetry.util.JwtUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private JwtUtil jwtUtil;

    @PostMapping("/register")
    public ApiResponse<Map<String, Object>> register(@RequestBody User user) {
        // 简化实现：不包含复杂的盐值和哈希，实际开发需加强
        userMapper.insert(user);
        String token = jwtUtil.generateToken(user.getUsername());
        Map<String, Object> data = new HashMap<>();
        data.put("token", token);
        data.put("user", user);
        return ApiResponse.success(data);
    }

    @PostMapping("/login")
    public ApiResponse<Map<String, String>> login(@RequestBody Map<String, String> creds) {
        String username = creds.get("username");
        String password = creds.get("password");

        User user = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, username)
                .eq(User::getPassword, password));

        if (user != null) {
            String token = jwtUtil.generateToken(username);
            Map<String, String> data = new HashMap<>();
            data.put("token", token);
            return ApiResponse.success(data);
        }
        return ApiResponse.error(401, "Invalid credentials");
    }
}
