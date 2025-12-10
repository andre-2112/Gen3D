# Role: You are a senior software developer, specialized in AWS architecture and deployments.

# Goal: Debug and fix issues related to the deployment of Meta's SAM3 an SAM3D on AWS, to extract 3d meshes from images - including the Gen3D Web App.

# Tasks:

## Task 1 - Read and Understand the architecture, concepts and deployments so far. This understanding is critical.

<base_documents>
    ~/docs/Gen3D - Architecture - 1.2.md
    ~/docs/Gen3D - Implementation Plan - 1.2.md
    ~/docs/SAM3-SAM3D - Arch - 1.2.mermaid
    ~/DEPLOYMENT_EXECUTION_REPORT.md
    ~/FINAL_DEPLOYMENT_REPORT.md
    ~/10 - PREVENTIVE-SOLUTIONS.md
    ~/12 - LOCAL-DEPLOYMENT-PLAN.md
    ~/13 - LOCAL-DEPLOYMENT-EXECUTION-REPORT.md
    ~/13 - PRODUCTION-DEPLOYMENT-PLAN.md

    # Highly Relevant:
    ~/14 - SAGEMAKER-DEPLOYMENT-REPORT.md
    ~/15 - END-TO-END-TEST-FAILURE-REPORT.md
    ~/15 - END-TO-END-TEST-FAILURE-REPORT-SUMMARY.md
</documents>

## Task 2 - Test the ec2 container for the issues reported.

Before executing Task 3, for the issues reported at "04-sagemaker\15 - END-TO-END-TEST-FAILURE-REPORT-SUMMARY.md", perform tests in the container on ec2, to try to reproduce the issues found on the SageMaker deployment.

The results of these tests should help the planning phase on Task 3, below.

## Task 3 - Create a New Plan for Local Deployment and Testing

Create a new document with the complete plan for local rebuild and re-deployment of a container capable of making the intended inferences on the SAM3 and SAM3D models. In one of the Architecture docs (Task #1), this local deployment plan was refered to as Phase 3A (I think - correct me if i am wrong or confirm).

This plan should include all of the steps to build the container, deploy it locally, test it locally, test the inferences wiht real data, validate that the inferences are working correctly with CORRECT OUTPUTS.

Highly Important:

Think, pre-empt and solve the issues found after SageMaker deployment ("04-sagemaker\15 - END-TO-END-TEST-FAILURE-REPORT-SUMMARY.md"). Plan to increase logging and debugging verbosity on the container, to reveal issues locally before a new SageMaker deployment (v2). Plan to include tests that will verify locally all of the issues reported on the remote (SageMaker) deployment - enhanced testing.

Include in the local deployment plan, a section with step by step instructions on how to test the inferences.

Include a script that should perform autmated enhanced testing of models.

## Task 4 - Preempt Additional Known Issues

<known_issues>

    - "Code files missing on EC2! Need to upload them. Let me read the local files first.      

    - "The build failed! Let me get the complete error details.

    - "I found the issue - there's a bash syntax error on line 17. The problem is with the $() command substitution in the JSON parameters array. Let me fix this by using a simpler command structure.

    - "The AWS CLI parameter escaping is problematic. Let me create a build script file and upload it to EC2 instead.

</known_issues>


