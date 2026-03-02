package com.example.poetryvisualization;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
@MapperScan("com.example.poetryvisualization.mapper")
public class PoetryVisualizationApplication {
  public static void main(String[] args) {
    SpringApplication.run(PoetryVisualizationApplication.class, args);
  }
}
