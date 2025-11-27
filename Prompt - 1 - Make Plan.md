# Role: You are a senior software developer, specialized in AWS architecture and deployments.

# Goal: Deploy Meta's new SAM 3D on AWS, to extract 3d meshes from images.

# Tasks:

## Task 1 - Read, Understand and Plan

        Go to the urls below, browse each url's whole site, 
        read all documents, installation instructions and source code. 
        While reading, do not just process words - understand the meaning.
        Do make an extra effort to understand the concepts and implementation details. 

        <read>
            https://github.com/facebookresearch/sam-3d-objects
            https://huggingface.co/facebook/sam-3d-objects
        </read>

        Main AWS services to be used in the deployment:

        <aws_resources>
            - IAM - Roles, Policies
            - CloudWatch
            - SageMaker 
            - Lambda - for the inference.
            - SES
            - S3
        </aws_resources>

        <observations>
            - Assume we already have account with AWS (Genesis3D) and HuggingFace.
            - We already got approval from Facebook, to use the HuggingFace model.
            - For this project, all names for new aws resources, should be preceded by "Gen3D".
        </observations>

       ### Subtasks:

        1.1 - Think well and plan all of the details of the implementation, according to the plan below.

        1.2 - Include all of the AWS CLI commands that will be used in the implementation.

        1.3 - Also include in the plan, a summarized but complete list of all of the AWS resources created.

        <plan>

            1 - Set up an S3 bucket to store input images and output 3D meshes.

                1.1 - Bucket will contain private folders for each user, where user images and meshes will be stored. 

                1.2 - Configure appropriate bucket policies and permissions to allow access from SageMaker and Lambda functions.
                
                1.3 - Additionally, create a folder called PUBLIC, where we will place a small web app/page to allow the user to submit images for processing.

                1.4 - Configure appropriate permissions to allow access to the files inside the PUBLIC folder.

            2 - Create a SageMaker notebook instance to develop and test the SAM 3D model. 

                2.2 - Configure it so its Async inference.

            3 - Configure SageMaker to use the SAM 3D model from Hugging Face for processing images.

                2.3 - Detail thiese configuration settings and steps in the Implementation Plan (below)

            4 - Develop Lambda functions to perform the following tasks:

                4.1 - Extract Lambda - Lambda function that triggers the SageMaker processing job when new images are uploaded to the S3 bucket.

                4.2 - Notify Lambda - Lambda to notify the user and admin (info@2112-lab.com) via email when a mesh becomes available. 

                    - Triggered the processing job is over and the output file has been generated and stored and available on S3. Use S3 event to trigger this lambda.

            5 - Implement error handling and admin notifications using AWS SES to alert on job failures.   

            6 - Set up logging using CloudWatch to monitor the processing jobs, lambdas invocations and notifications.
            
            7 - Test the entire workflow end-to-end to ensure images are processed correctly and 3D meshes are generated. Download some test image from the internet, for the testing. Use curl for the testing and show the commands used. Use fictitous users for the testing.

            8 - Design and implement a simple html page that will allow the drag and drop of an image, then mouse selection of bounding boxes around the objets that the user intend to extract meshes from. Upload this web page to the PUBLIC folder in the S3 bucket.

            9 - Perform additional end-to-end testing, using the html page above.

            10 - Suggest improvements in the implemented framework and deployed service.

        </plan>

        Generate 3 documents from the well thought out detailed plan. Store them in the current working directory.

## Task 2 - Document

        1 - Gen3D - Architecture - 1.0.md" - The complete, tuthoritative guide for the framewoek implementation of Gen3D - a Generative3D service for extracting 3D meshes from images. Include architecture diagram showing the main architectural compoentns and relevant flows.

        2 - "Gen3D - Implementation Plan - 1.0.md" - The complete and detailed impementation plan. Include architecture diagram showing the flows and another diagram showing how the aws resources will be used. This document will be used as the based for the development, implementation and deplyment.

        3 - "Gen3D - AWS Resources - 1.0.md" - A summarized but complete list of all of the AWS resources created.  

        4 - "Gen3D - User Guide - 1.0.md - A User's Guide for the lambda query service.
    







