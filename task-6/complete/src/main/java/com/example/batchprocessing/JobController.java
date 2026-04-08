package com.example.batchprocessing;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.Job;
import org.springframework.batch.core.JobExecution;
import org.springframework.batch.core.JobParameters;
import org.springframework.batch.core.JobParametersBuilder;
import org.springframework.batch.core.launch.JobLauncher;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/jobs")
public class JobController {

    private static final Logger log = LoggerFactory.getLogger(JobController.class);

    @Autowired
    private JobLauncher jobLauncher;

    @Autowired
    private Job importProductJob;

    @PostMapping("/trigger")
    public ResponseEntity<Map<String, Object>> triggerJob(HttpServletRequest request) {
        String uri = request.getRequestURI();
        log.info("Batch job trigger requested: uri={}", uri);

        try {
            JobParameters params = new JobParametersBuilder()
                    .addLong("timestamp", System.currentTimeMillis())
                    .toJobParameters();

            JobExecution execution = jobLauncher.run(importProductJob, params);

            log.info("Batch job completed: uri={}, executionId={}, status={}",
                    uri, execution.getId(), execution.getStatus());

            return ResponseEntity.ok(Map.of(
                    "jobExecutionId", execution.getId(),
                    "status", execution.getStatus().toString(),
                    "uri", uri
            ));
        } catch (Exception e) {
            log.error("Batch job failed: uri={}, error={}", uri, e.getMessage(), e);
            return ResponseEntity.internalServerError().body(Map.of(
                    "error", e.getMessage(),
                    "uri", uri
            ));
        }
    }
}
