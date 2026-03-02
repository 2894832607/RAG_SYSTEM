-- ============================================================
-- Poetry RAG System — 完整数据库建表脚本
-- 适用数据库: MySQL 8.0+
-- 字符集:     utf8mb4 (支持中文及emoji)
-- ============================================================

-- 1. 创建数据库
CREATE DATABASE IF NOT EXISTS poetry_rag
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE poetry_rag;

-- ============================================================
-- 2. 系统用户表 (sys_user)
--    用途: 管理登录用户信息，后期可接入 Spring Security
-- ============================================================
DROP TABLE IF EXISTS sys_user;
CREATE TABLE sys_user (
    id              BIGINT          PRIMARY KEY AUTO_INCREMENT          COMMENT '主键ID',
    username        VARCHAR(50)     NOT NULL                            COMMENT '登录用户名',
    password        VARCHAR(255)    NOT NULL                            COMMENT '密码(BCrypt加密存储)',
    nickname        VARCHAR(50)     DEFAULT ''                          COMMENT '用户昵称',
    avatar          VARCHAR(512)    DEFAULT ''                          COMMENT '头像URL',
    status          TINYINT         NOT NULL DEFAULT 1                  COMMENT '账号状态: 1=正常, 0=禁用',
    gmt_create      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间',
    gmt_modified    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP         COMMENT '更新时间',
    UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';


-- ============================================================
-- 3. 生图任务流转表 (sys_generation_task)  —— 核心表
--    用途: 记录每一次诗词可视化任务的全生命周期
--    状态机: PENDING(0) → COMPLETED(1) / FAILED(2)
-- ============================================================
DROP TABLE IF EXISTS sys_generation_task;
CREATE TABLE sys_generation_task (
    id               BIGINT          PRIMARY KEY AUTO_INCREMENT          COMMENT '物理主键',
    task_id          VARCHAR(64)     NOT NULL                            COMMENT '分布式任务追踪ID(UUID)',
    user_id          BIGINT          DEFAULT NULL                        COMMENT '关联提交任务的用户ID',
    original_poem    VARCHAR(255)    NOT NULL                            COMMENT '用户输入的原始古诗句',
    retrieved_text   TEXT            DEFAULT NULL                        COMMENT 'RAG检索到的现代文译文/知识',
    enhanced_prompt  TEXT            DEFAULT NULL                        COMMENT '最终注入SD模型的正向提示词',
    result_image_url VARCHAR(512)    DEFAULT NULL                        COMMENT '生成图像的访问路径',
    task_status      TINYINT         NOT NULL DEFAULT 0                  COMMENT '任务状态: 0=排队/生成中, 1=成功, 2=失败',
    error_message    VARCHAR(512)    DEFAULT NULL                        COMMENT '失败时的异常原因',
    gmt_create       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '记录创建时间',
    gmt_modified     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                     ON UPDATE CURRENT_TIMESTAMP         COMMENT '记录最后更新时间',
    UNIQUE KEY uk_task_id    (task_id),
    KEY        idx_user_id   (user_id),
    KEY        idx_status    (task_status),
    KEY        idx_create    (gmt_create)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='生图任务流转表';


-- ============================================================
-- 4. 用户收藏表 (sys_favorite)
--    用途: 用户可收藏/点赞自己或他人的优秀生成作品
-- ============================================================
DROP TABLE IF EXISTS sys_favorite;
CREATE TABLE sys_favorite (
    id              BIGINT          PRIMARY KEY AUTO_INCREMENT          COMMENT '主键ID',
    user_id         BIGINT          NOT NULL                            COMMENT '用户ID',
    task_id         VARCHAR(64)     NOT NULL                            COMMENT '收藏的任务ID',
    gmt_create      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '收藏时间',
    UNIQUE KEY uk_user_task (user_id, task_id),
    KEY        idx_user_id  (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户收藏表';


-- ============================================================
-- 5. 初始测试数据
-- ============================================================
INSERT INTO sys_user (username, password, nickname) VALUES
    ('admin', '$2a$10$N.zmdr9k7uOCQbFnRpwoJOkXRLh0MzD0hkaOA7.68xui5xaKtUUSm', '管理员'),
    ('test',  '$2a$10$N.zmdr9k7uOCQbFnRpwoJOkXRLh0MzD0hkaOA7.68xui5xaKtUUSm', '测试用户');

-- 插入一条示例任务数据，方便前端联调时验证
INSERT INTO sys_generation_task (task_id, user_id, original_poem, task_status) VALUES
    ('demo-0001-0001-0001', 1, '大漠孤烟直，长河落日圆', 0);
