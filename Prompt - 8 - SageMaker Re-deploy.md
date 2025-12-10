# Role: You are a senior software developer, specialized in AWS architecture and deployments.

# Goal: Plan the implementation and deployment of AWS infrastructure to extract 3d meshes from images, using SAM3 and SAM3D on AWS.

# Tasks:

- Read all tasks before starting to execute.

- If any process exceeds output token limits, then break the process or output in smaller chnucks.

## Task 1 - Read the architecture documents

    Read the ALL of the documents below. 

    The following is critical: Do not just read words. Understand the architecture, the concepts, the flows and the implementation. Do not skip this understanding.

    Pay particular attention to the goal of using SageMaker Async Inferences, with SAM3 and SAM3D models and inferences.

    Observation: Some of the documents might be "slightly" outdated or have some implementation mistakes, specially related to the SageMaker deployment.

    "./docs/Gen3D - Architecture - 1.2.md"
    "./docs/Gen3D - Implementation Plan - 1.2.md"
    "./docs/Gen3D - AWS Resources - 1.2.md"

    Understand this flow:

    "./docs/SAM3-SAM3D - Arch - 1.2.mermaid"

    Understand what it has been done so far.
    Understand and remember the issues described in the documents below,
    Understand what the high and low level solutions that would prevent the issues from occuring.

    "./1 - DEPLOYMENT_EXECUTION_REPORT.md"I fixe
    "./2 - FINAL_DEPLOYMENT_REPORT.md"
    "./deployment/3 - DEPLOYMENT_SUMMARY.md"
    "./deployment/04-sagemaker/4 - DEPLOYMENT-SUMMARY.md
    "./deployment/04-sagemaker/5 - ENDPOINT-FAILURE-DIAGNOSIS.md  
    "./deployment/04-sagemaker/6 - ASYNC-INFERENCE-MIGRATION.md
    "./deployment/04-sagemaker/7 - ASYNC-ENDPOINT-FAILURE-DIAGNOSIS.md
    "./deployment/04-sagemaker/8 - COMPLETE-FIX-PLAN.md

## Task 2 - List All Issues

    - Create a new document with a list of all of the issues you encountered in the installation (dockerfile, ec2, sagemaker, flask, endpoints) and deployment of sam3 and sam3d with sagemaker asyncronous endpoints. 

    - Include high level issues issues related to architecture design.

    - Include low level issues such as the one below:

    <issue>
        Found the issue! The Docker build is stuck on tzdata.config - the timezone
        configuration package is waiting for interactive input. The process tree shows:

        apt-get(1329)---dpkg(2271)---frontend(2284)---tzdata.config(2293)

        This is blocking the build. I need to fix the Dockerfile to avoid interactive
        prompts by setting DEBIAN_FRONTEND=noninteractive. 
    </issue>

● Code files missing on EC2! Need to upload them. Let me read the local files first:      

    - The list of issues in this document, should be summarized. This document should be short and sumarized.

## Task 3 - List All Preventive Solutions

    - Create a new document with the list of steps that should have been proactively taken, to prevent each and all of the issues.

    - For each list from Task #2, THINK, PLAN and DESCRIBE the solutions to prevent the issue from happening again in the next deployment.

## Task 4 - Assess Current State

    4.1 - Assess which resources are still deployed.

    4.2 - I see an EC2 Instance still deployed: i-042ca5d5485788c84

    4.3 - Does this instance have a build container already? If so, is it properly configured? can it be utilized?

    4.4 - Does this instance already have a copy of the models (sam3 and sam3d) downloaded? 
    
        4.4.1 - If so, show my their path.
        4.4.2 - If so, it would be nice to be able to reuse these downloaded models to mane new containers, if necessary and possible. would it be possible to build new containers in this ec2 instance, if there is a need for us to build a new container?

## Task 5 - Create a New Plan for Local Deployment and Testing

    Create a new document with the complete plan for local deployment of a container capable of making the intended inferences on the SAM3 and SAM3D models. In one of the Architecture docs (Task #1), this local deployment plan was refered to as Phase 3A (I think - correct me if i am wrong or confirm).

    This plan should include all of the steps to build the container, deploy it locally, test it locally, and validate that the inferences are working correctly.

    Include in the local deployment plan, a section with step by step instructions on how to test the inferences.

    Include a script that should perform autmated testing of models.

    This local deployment should be independent.

    Answer the following questions and add it to the document: Despite the local deployment being independent, could it be re-utilized in the remote deployment? If so, how exactly? What would be the requirements for the local the deployment, in order to be used in the remote (SageMaker) deployment? 

## Task 6 - Create a New Procution Plan

    This is your main task: Your main task is to think really well and create a new implementation plan for a service that uses SageMaker Asynchronous Inferences of Sam3 and SAM3D models, according to the flow and invocations described in the architecture documents above (Task #1).

    Your plan should include preventive measures and a design that completely avoids the issues in the first deployment attempt and subsequent deployment corrections and failures.

    The plan should include all of the steps to deply and configure SageMaker for inferences with SAM3 and SAM3D. 
    
    The plan should include the review and reuse of exising resources such as roles and policies, or the creation of new ones. 

    The plan should re-use excisting S3 bucket and defined folder structures.

    The plan should not include cognito, dynamo, or the web-app. 

    The plan is about SagemMaker Async INferences of SAM3 and SAM3D.

    The plan should re-use any existing container, if possible, RELIABLY and TESTED. Or create a new container.

    The plan should re-use the already downlaoded SAM3 and SAM3D models, if available inside the current EC3 instance, or if a new instance becomes needed, download the models again.
    
    REMEMBER: Should new downloads become necessary, the SAM3 and SAM3D models are available at the S3 urls below:

        SAM3 = s3://gen3d-data-bucket/models/sam3
        SAM3D = s3://gen3d-data-bucket/models/sam3d

    This is critical: Break the plan in main steps/phases and ensure the plan includes verification methods for each main step in the implementation.

    Include in the plan, a section with step by step instructions on how to test the inferences - using curl, if possible.

    Include a script that should perform autmated testing of the inferences.

