package com.example.poetryvisualization.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("sys_chat_message")
public class ChatMessage {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private String sessionId;

    private String userMessage;

    private String aiReply;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime gmtCreate;
}
