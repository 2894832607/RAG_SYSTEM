# Backend Spring Boot 3.5 — 多阶段构建
#
# Stage 1 (builder): Maven 构建 FAT JAR
# Stage 2 (runtime): JRE 17-slim 最小化运行时
#
# 构建命令：
#   docker build -t poetry-backend:latest ./backend
#
# 运行命令（独立，需外部 MySQL）：
#   docker run -p 8080:8080 \
#     -e DB_URL="jdbc:mysql://host:3306/poetry_rag?..." \
#     -e DB_USERNAME=poetry \
#     -e DB_PASSWORD=your_pass \
#     -e AI_SERVICE_URL="http://ai-service:8000" \
#     -e JWT_SECRET="your_32char_secret" \
#     poetry-backend:latest

# ── Stage 1：Maven 构建 ───────────────────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-17-alpine AS builder

WORKDIR /build

# 先复制 pom.xml，利用 Docker 层缓存，仅依赖变化时才重新下载
COPY pom.xml ./
RUN mvn dependency:go-offline -q

# 复制源码并打包（跳过测试）
COPY src ./src
RUN mvn package -DskipTests -q

# ── Stage 2：轻量运行时 ───────────────────────────────────────────────────────
FROM eclipse-temurin:17-jre-alpine

# 安全：非 root 用户运行
RUN addgroup -S poetry && adduser -S poetry -G poetry
WORKDIR /app

# 从构建阶段复制 JAR
COPY --from=builder /build/target/poetry-visualization-*.jar app.jar

# 健康检查（需要 curl 或 wget）
RUN apk add --no-cache curl

EXPOSE 8080

# JVM 优化：减少容器内存使用
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -Djava.security.egd=file:/dev/urandom"

USER poetry

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
