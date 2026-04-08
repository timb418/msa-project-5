FROM openjdk:17-slim
# 8080
WORKDIR .
COPY build/libs/*.jar app.jar
ENTRYPOINT ["java","-jar","/app.jar"]