# Stage 1: Build
FROM gradle:8.8-jdk17 AS builder
WORKDIR /app
COPY build.gradle settings.gradle ./
COPY gradle gradle
COPY src src
RUN gradle bootJar --no-daemon

# Stage 2: Run
FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
