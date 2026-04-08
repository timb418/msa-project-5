FROM gradle:8.8-jdk17
# 8080
WORKDIR /app
COPY build/libs/*.jar app.jar
ENTRYPOINT ["java","-jar","/app/app.jar"]