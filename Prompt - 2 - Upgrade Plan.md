# Role: You are a senior software developer, specialized in AWS architecture and deployments.

# Goal: Develop a concise plan to deploy Meta's SAM3 an SAM3D on AWS, to extract 3d meshes from images.

# Tasks:

## Task 1 - Read and Understand 

### 1.1 - Understand SAM3 and SAM3D

    - Go to the urls below, browse each url's whole site.
    - Read all documents, installation instructions and source code. 
    - While reading, do not just process words - understand the meaning.
    - Do make an extra effort to understand the concepts and implementation details. 

    <framework_urls>
        https://github.com/facebookresearch/sam3
        https://huggingface.co/facebook/sam3
        https://github.com/facebookresearch/sam-3d-objects
        https://huggingface.co/facebook/sam-3d-objects
    </framework_urls>

### 1.2 - Understand Current Architecture

    - Re-read all documents below. 
    - While reading, do not just process words - understand the meaning.
    - Do make an extra effort to understand the concepts and implementation details. 

    - Observation: Understand that Architecture 1.0 did not detail the mask creation process.

    <current_architecture>
        ~/docs/Gen3D - Architecture - 1.0.md
        ~/docs/Gen3D - Implementation Plan - 1.0.md
        ~/docs/Gen3D - AWS Resources - 1.0.md
    </current_architecture>

### 1.3  - Understand Architecture Upgrade

    - Understand the architecture upgrade, its flows, interactivity and asynchronous processes.
    
    <architecture_upgrade>

        The architecture upgrade includes a **Hybrid Split** approach:

        1. **Heavy Compute (Server):** Image Encoding & 3D Reconstruction.  
        2. **Interactive Compute (Client):** Mask Decoding & User Guidance.

        ## **Logical Workflow (The "Hybrid" Pattern)**

        ### **Stage 1: Initialization**

        1. **User** uploads an RGB image to S3.  
        2. **Client** requests "Initialization" from SageMaker.  
        3. **SageMaker** runs **SAM 3 Image Encoder** (ViT-H).  
        4. **SageMaker** returns **Image Embeddings** (approx. 4MB) to the client.

        ### **Stage 2: Interaction (Client-Side)**

        1. **Client** loads the **SAM Mask Decoder** (ONNX model) in the browser.  
        2. **User** clicks on the object.  
        3. **Browser** runs the ONNX model using the *Embeddings* \+ *Click Coordinates*.  
        4. **Result:** Instant mask generation (milliseconds) with zero server latency.  
        5. **User** confirms the selection.

        ### **Stage 3: 3D Reconstruction (Server-Side)**

        1. **Client** uploads the final binary mask (PNG) to S3.  
        2. **Client** triggers the "Reconstruct" job on SageMaker.  
        3. **SageMaker** loads **SAM 3D**.  
        4. **SageMaker** inputs the *Original Image* \+ *Binary Mask*.  
        5. **Result:** A 3D Mesh (.obj/.glb) is generated and saved to S3.

    </architecture_upgrade>

### 1.4  - Understand Architecture Upgrade Details

    - Read all documents below. 
    - While reading, do not just process words - understand the meaning.
    - Do make an extra effort to understand the concepts and implementation details. 

    - Important: Understand the changes necessary to the current architecture; to integrate the new upgrade features (including the interactive, mask creation process).

    <architecture_upgrade_details>
        ~/docs/SAM3-SAM3D - Arch - 1.2.md
        ~/docs/SAM3-SAM3D - Arch - 1.2.mermaid
    </architecture_upgrade_details>


## Task 2 - Plan Upgrade

    For each of the planning subtasks below:

    - Think deeply - Think all of the details related to each topic in the subtask.
    - Think wide - Think how each topic relates to other topics.

### 2.1 - Initial Setup: IAM, S3 

    2.1.1 - Plan for an S3 bucket and a folder structure that integrates the current architecture with the new features (including interactive mask generation).

    2.1.2 - Plan all of the necessary IAM Policies and Roles, for each of the AWS resources created, including the resources created by the steps below.

### 2.2 - Sagemaker 

    2.2.1 - Plan to confiugure SageMaker, according to the  "~/docs/SAM3-SAM3D - Arch - 1.2.md" document:
        
    2.2.2- Plan the implementation of interactive mask generation with the "Hybrid Split" approach. 

        - Plan all of the necessary actions by the user.
        - Plan all of the requests and responses.
        - Plan all of the inputs and outputs.

    2.2.3 - Plan the implementation of 3D reconstruction (to point cloud), with the single container approach.

        - Plan all of the requests and responses.
        - Plan all of the inputs and outputs.

    2.2.4 - Plan the installation of the SAM3 and SAM3D models from HuggingFace.

    2.2.5 - Plan to configure SageMaker Async, to use SAM3 and SAM3D models, in a "Single Container".
    
        SageMaker Endpoint (Async):

            - The Container: You build a single Docker container (using AWS Deep Learning Containers) that installs both SAM 3 and SAM 3D.

            - The Instance: Configured to use a GPU instance (e.g., ml.g5.xlarge).

            - Auto-scaling: Configured to min_instances=0. When the queue is empty, AWS shuts down the GPU (saving you $\approx$ $1-2/hour).

    2.2.6 - Plan the implementation of error handling and admin notifications using AWS SES to alert on job failures.   

    2.2.7 - Detail all of these configuration settings and steps in the Implementation Plan (below).

### 2.3 - Lambdas 

    DevePlan the development of Lambda functions to perform the following tasks:

    2.3.1 - Wrapper Lambda - Lambda function that wraps SageMaker invocations.

        - Ensure this Lambda supports all of the endpoints necesary for all request/responses realted to the initialization, interaction and 3d reconstructions steps.

        - Detail this Lambda in the Architecture document (below).

    2.3.2 - Notify Lambda - Lambda to notify the user and admin (info@2112-lab.com) via email when a mesh becomes available. 

        - Triggered the processing job is over and the output file has been generated and stored and available on S3. Use S3 event to trigger this lambda.

    2.3.3 - Implement Lambda error handling and admin notifications using AWS SES to alert on job request failures.   

### 2.4 - Logging 

    - Plan the logging using CloudWatch to monitor SageMaker requests and processing jobs; lambdas invocations and SES notifications.

### 2.5 - Testing 

    - Plan tests for the entire end-to-end workflow, ensuring each indivudual step in the workflow is working as intended, as well as the system as a whoile. Download some test image from the internet, for the testing. Use curl for the testing and show the commands used. Use fictitious users for the testing.


## Task 3 - Gen3D Web App

### 3.1 - Design and implement 

    - Plan the development of a demo/test web application, similar to Meta's SAM3D demo page at:

    https://aidemos.meta.com/segment-anything/editor/convert-image-to-3d/

    - Ensure that implementation follow flow defined in the "SAM3-SAM3D - Arch - 1.2.mermaid" document

    - Ensure planned implementation includes the following features:

        - Multi-step process.
        - Image selection / submition.
        - S3 storage.
        - Embeddings retrieval.
        - Mask selection / definition - Iteractively.
        - Mask submition.
        - 3d reconstruction.
        - Point Cloud download.
        - Point Cloud rendering.

### 3.2 - Upload and Deploy

    - Upload this web app to the PUBLIC folder in the S3 bucket. 

    - Plan and provide suggestions to make this S3 deployment of the app availalbe for use.

    - Will CloudFront or Amplify be necessary?

    - We do like Amplify Storage (with Cognito Authentication) for Web Apps.

### 3.3 - Test

    - Plan detailed steps for end-to-end testing, using the web app above.


## Task 4 - Document

Based on all of the planning above write the following new markdoown documents:

### 4.1 - Gen3D - Architecture - 1.2.md" - The complete, authoritative guide for the framework implementation of Gen3D - a Generative3D service for extracting 3D meshes from images. 

    - Include the new architectural features and flow upgrades described above.

    - Include architecture diagram showing the main architectural components and relevant flows.

    - Exclude all source code.

### 4. 2 - "Gen3D - Implementation Plan - 1.2.md" - The complete and detailed, upgraded implementation plan. 

    This document will be used as the based for the development, implementation and deployment.

    - Include architecture diagram showing the flows and another diagram showing how the aws resources will be used. 

    - Include all of the requirements and installations for this implementation.

    - Include all of the AWS resources that will be created for this implementation.

    - Include all of the AWS CLI commands that will be used in the implementation.

    - Include source code for:
        - Sagemaker Image Dockerfile
        - Inference Script (inference.py)
        - Wrapper Lambda
        - Notifications Lambda

    - Exclude source code for the Gen3D Web App.

### 4.3 - "Gen3D - Web App - 1.2.md" - The complete and detailed implementation of the Gen3D Web App.

    - Include flow diagram, illustrating the 3 requests/responses/processes:

        - Initialization
        - Interaction
        - Recosontruction

    - Include a "User Guide" section.

    - Include all of the Web app source code - at the end of the document.


### 4.4 - "Gen3D - AWS Resources - 1.2.md" - A summarized but complete list of all of the AWS resources created.  

### 4.5 - "Gen3D - User Guide - 1.2.md" - A User's Guide.

    - Include Image Selection / Upload
    - Include Mask Creation / Submition
    - 3D Reconstruction / Download / Rendering
    
## Task 5 - Questions 

    5.1 - Should the Initialization step be synchornous or asynchronous?

    5.2 - Should we make the point cloud conversion part of the 3d reconstruction process?

    5.3 - Should we have a separate process for converting point cloud to mesh?

    5.4 - If we decide to have separate processes, should we reuse the container built with SAM3 and SAM3D, install Open3D in and run this augmented container for the lambda that does only point cloud conversion?

    5.5 - Suggest the top 2 or 3 best approaches to convert the point cloud output from the 3D reconstruciton process, into a threejs compatible mesh.

    5.6 - Suggest improvements in the implemented framework and deployed service.

## Task 6 - Persist

    - DO NOT STOP UNTIL ALL TASKS ABOVE ARE COMPLETELY (100%) DONE.

    - DO NOT STOP UNTIL END-TO-END TESTING IS SUCCESSFULL.
