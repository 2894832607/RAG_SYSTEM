package com.example.poetryvisualization.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import io.swagger.v3.oas.models.servers.Server;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

/**
 * OpenAPI 3.0 (Swagger) 全局配置。
 *
 * <p>访问地址：
 * <ul>
 *   <li>Swagger UI：<a href="http://localhost:8080/swagger-ui/index.html">/swagger-ui/index.html</a></li>
 *   <li>OpenAPI JSON：<a href="http://localhost:8080/v3/api-docs">/v3/api-docs</a></li>
 *   <li>OpenAPI YAML：<a href="http://localhost:8080/v3/api-docs.yaml">/v3/api-docs.yaml</a></li>
 * </ul>
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI poetryRagOpenAPI() {
        final String tokenSchemeName = "bearerAuth";

        return new OpenAPI()
                .info(new Info()
                        .title("Poetry RAG System — Backend API")
                        .description("""
                                诗词 RAG 可视化系统后端接口文档。
                                
                                **认证方式**：受保护接口需在请求头携带 `Authorization: <token>`（登录后获取）。
                                
                                **服务依赖**：部分接口（`/visualize`、`/think-stream`）会异步调用 AI 微服务（FastAPI，默认 `:8000`）。
                                """)
                        .version("0.1.0")
                        .contact(new Contact()
                                .name("Poetry RAG Team")
                                .url("https://github.com/your-org/Poetry-RAG-System"))
                        .license(new License()
                                .name("MIT")
                                .url("https://opensource.org/licenses/MIT")))
                .servers(List.of(
                        new Server().url("http://localhost:8080").description("本地开发"),
                        new Server().url("http://127.0.0.1:8080").description("本地回环")))
                .addSecurityItem(new SecurityRequirement().addList(tokenSchemeName))
                .components(new Components()
                        .addSecuritySchemes(tokenSchemeName,
                                new SecurityScheme()
                                        .name("Authorization")
                                        .type(SecurityScheme.Type.APIKEY)
                                        .in(SecurityScheme.In.HEADER)
                                        .description("登录后返回的 token，直接填入（不含 Bearer 前缀）")));
    }
}
