# Gen3D - AWS Resources v1.0

## Complete List of AWS Resources

This document provides a comprehensive, authoritative list of all AWS resources created for the Gen3D service deployment.

---

## Resource Summary

| Service | Resource Count | Purpose |
|---------|---------------|---------|
| IAM | 3 Roles + 3 Policies | Access control and permissions |
| S3 | 2 Buckets | Data and model storage |
| SageMaker | 1 Model + 1 Config + 1 Endpoint | ML inference |
| Lambda | 2 Functions | Workflow orchestration |
| ECR | 1 Repository | Container storage |
| SES | 2 Email Identities | Notifications |
| CloudWatch | 3 Log Groups + 2 Alarms + 1 Dashboard | Monitoring |

**Total Resource Count**: 20 AWS resources

---

## 1. IAM Resources

### 1.1 IAM Roles (3)

#### Gen3DSageMakerExecutionRole
- **Type**: IAM Role
- **ARN**: `arn:aws:iam::{ACCOUNT_ID}:role/Gen3DSageMakerExecutionRole`
- **Purpose**: Execution role for SageMaker endpoint
- **Trusted Entity**: `sagemaker.amazonaws.com`
- **Attached Policies**:
  - Gen3DSageMakerPolicy (inline)
- **Permissions**:
  - S3: GetObject, PutObject, ListBucket on gen3d-* buckets
  - CloudWatch: CreateLogGroup, CreateLogStream, PutLogEvents
  - ECR: GetDownloadUrlForLayer, BatchGetImage, BatchCheckLayerAvailability

#### Gen3DLambdaExtractRole
- **Type**: IAM Role
- **ARN**: `arn:aws:iam::{ACCOUNT_ID}:role/Gen3DLambdaExtractRole`
- **Purpose**: Execution role for Extract Lambda function
- **Trusted Entity**: `lambda.amazonaws.com`
- **Attached Policies**:
  - Gen3DLambdaExtractPolicy (inline)
- **Permissions**:
  - S3: GetObject, ListBucket on input paths
  - SageMaker: InvokeEndpointAsync
  - CloudWatch: Log writing

#### Gen3DLambdaNotifyRole
- **Type**: IAM Role
- **ARN**: `arn:aws:iam::{ACCOUNT_ID}:role/Gen3DLambdaNotifyRole`
- **Purpose**: Execution role for Notify Lambda function
- **Trusted Entity**: `lambda.amazonaws.com`
- **Attached Policies**:
  - Gen3DLambdaNotifyPolicy (inline)
- **Permissions**:
  - S3: GetObject, ListBucket on output paths
  - SES: SendEmail, SendRawEmail
  - CloudWatch: Log writing

### 1.2 IAM Policies (3)

#### Gen3DSageMakerPolicy
- **Type**: Inline Policy
- **Attached To**: Gen3DSageMakerExecutionRole
- **Permissions**: S3, CloudWatch, ECR access

#### Gen3DLambdaExtractPolicy
- **Type**: Inline Policy
- **Attached To**: Gen3DLambdaExtractRole
- **Permissions**: S3, SageMaker, CloudWatch access

#### Gen3DLambdaNotifyPolicy
- **Type**: Inline Policy
- **Attached To**: Gen3DLambdaNotifyRole
- **Permissions**: S3, SES, CloudWatch access

---

## 2. S3 Resources

### 2.1 S3 Buckets (2)

#### gen3d-data-bucket
- **Type**: S3 Bucket
- **ARN**: `arn:aws:s3:::gen3d-data-bucket`
- **Region**: us-east-1
- **Purpose**: Primary data storage for inputs, outputs, and web interface
- **Size**: Variable (grows with usage)
- **Configuration**:
  - Versioning: Enabled
  - Encryption: SSE-S3 (AES256)
  - Static Website Hosting: Enabled
  - CORS: Configured for browser uploads
  - Event Notifications: Configured for Lambda triggers
- **Folder Structure**:
  ```
  /public/                    (Website files)
  /users/{user_id}/input/     (Upload triggers)
  /users/{user_id}/output/    (Output triggers)
  /sagemaker-output/          (Async inference outputs)
  ```
- **Access**:
  - Public read for /public/*
  - IAM role-based for other paths
- **Lifecycle Policies**: (Optional) Archive to Glacier after 90 days

#### gen3d-model-bucket
- **Type**: S3 Bucket
- **ARN**: `arn:aws:s3:::gen3d-model-bucket`
- **Region**: us-east-1
- **Purpose**: Storage for SAM 3D model artifacts and checkpoints
- **Configuration**:
  - Versioning: Disabled
  - Encryption: SSE-S3 (AES256)
- **Folder Structure**:
  ```
  /sam3d-model/checkpoints/
  /sam3d-model/config/
  ```
- **Access**: SageMaker execution role only

---

## 3. SageMaker Resources

### 3.1 SageMaker Model

#### Gen3DSAM3DModel
- **Type**: SageMaker Model
- **ARN**: `arn:aws:sagemaker:us-east-1:{ACCOUNT_ID}:model/gen3dsam3dmodel`
- **Purpose**: SAM 3D inference model definition
- **Container Image**: `{ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/gen3d-sam3d-inference:latest`
- **Model Data**: Embedded in container
- **Execution Role**: Gen3DSageMakerExecutionRole
- **Mode**: SingleModel

### 3.2 SageMaker Endpoint Configuration

#### Gen3DSAM-AsyncConfig
- **Type**: Endpoint Configuration
- **ARN**: `arn:aws:sagemaker:us-east-1:{ACCOUNT_ID}:endpoint-config/gen3dsam-asyncconfig`
- **Purpose**: Configuration for async inference endpoint
- **Production Variants**:
  - **Variant Name**: AllTraffic
  - **Model**: Gen3DSAM3DModel
  - **Instance Type**: ml.g4dn.xlarge
  - **Instance Count**: 1 (auto-scaling enabled)
  - **Initial Weight**: 1.0
- **Async Inference Config**:
  - **Output S3 Path**: s3://gen3d-data-bucket/sagemaker-output/
  - **Max Concurrent Invocations**: 4 per instance
- **Estimated Cost**: ~$0.736/hour per instance

### 3.3 SageMaker Endpoint

#### Gen3DSAMAsyncEndpoint
- **Type**: Async Inference Endpoint
- **ARN**: `arn:aws:sagemaker:us-east-1:{ACCOUNT_ID}:endpoint/gen3dsamasyncendpoint`
- **Purpose**: Production endpoint for 3D mesh generation
- **Endpoint Config**: Gen3DSAM-AsyncConfig
- **Status**: InService
- **Creation Time**: [Set during deployment]
- **Last Modified**: [Updated during deployment]
- **Data Capture**: Disabled (can be enabled for monitoring)

---

## 4. Lambda Resources

### 4.1 Lambda Functions (2)

#### Gen3DExtractLambda
- **Type**: Lambda Function
- **ARN**: `arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:Gen3DExtractLambda`
- **Purpose**: Orchestrates SageMaker invocation on image upload
- **Runtime**: Python 3.11
- **Handler**: lambda_function.lambda_handler
- **Memory**: 512 MB
- **Timeout**: 30 seconds
- **Execution Role**: Gen3DLambdaExtractRole
- **Environment Variables**:
  - `SAGEMAKER_ENDPOINT_NAME`: Gen3DSAMAsyncEndpoint
  - `DATA_BUCKET`: gen3d-data-bucket
  - `ADMIN_EMAIL`: info@2112-lab.com
- **Triggers**: S3 PUT events on `users/*/input/*.png`
- **Concurrency**: Reserved 100
- **Estimated Invocations**: Variable based on usage
- **Cost**: ~$0.0000002/invocation

#### Gen3DNotifyLambda
- **Type**: Lambda Function
- **ARN**: `arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:Gen3DNotifyLambda`
- **Purpose**: Sends email notifications on completion
- **Runtime**: Python 3.11
- **Handler**: lambda_function.lambda_handler
- **Memory**: 256 MB
- **Timeout**: 15 seconds
- **Execution Role**: Gen3DLambdaNotifyRole
- **Environment Variables**:
  - `DATA_BUCKET`: gen3d-data-bucket
  - `ADMIN_EMAIL`: info@2112-lab.com
  - `SOURCE_EMAIL`: noreply@genesis3d.com
- **Triggers**: S3 PUT events on `users/*/output/*.ply`
- **Concurrency**: Reserved 50
- **Estimated Invocations**: Variable based on usage
- **Cost**: ~$0.0000002/invocation

---

## 5. ECR Resources

### 5.1 ECR Repository

#### gen3d-sam3d-inference
- **Type**: ECR Repository
- **ARN**: `arn:aws:ecr:us-east-1:{ACCOUNT_ID}:repository/gen3d-sam3d-inference`
- **URI**: `{ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/gen3d-sam3d-inference`
- **Purpose**: Stores custom Docker image for SageMaker inference
- **Image Tag**: latest
- **Image Size**: ~8-10 GB (includes PyTorch, SAM 3D model, dependencies)
- **Scan on Push**: Enabled (recommended)
- **Lifecycle Policy**: Keep last 5 images
- **Access**: SageMaker execution role

---

## 6. SES Resources

### 6.1 Verified Email Identities (2)

#### Admin Email
- **Type**: SES Email Identity
- **Email**: info@2112-lab.com
- **Status**: Verified
- **Purpose**: Receive all notifications and error alerts
- **Verification**: Email verification link

#### Source Email
- **Type**: SES Email Identity
- **Email**: noreply@genesis3d.com
- **Status**: Verified
- **Purpose**: Sender address for automated emails
- **Verification**: Email verification link

### 6.2 SES Configuration

- **Sending Quota**:
  - Sandbox: 200 emails/day
  - Production: Request limit increase as needed
- **Sending Rate**: 1 email/second (sandbox)
- **Region**: us-east-1
- **Reputation**: Monitor via SES console

---

## 7. CloudWatch Resources

### 7.1 Log Groups (3)

#### /aws/lambda/Gen3DExtractLambda
- **Type**: CloudWatch Log Group
- **ARN**: `arn:aws:logs:us-east-1:{ACCOUNT_ID}:log-group:/aws/lambda/Gen3DExtractLambda`
- **Purpose**: Logs for Extract Lambda function
- **Retention**: 30 days
- **Estimated Size**: Variable based on invocations

#### /aws/lambda/Gen3DNotifyLambda
- **Type**: CloudWatch Log Group
- **ARN**: `arn:aws:logs:us-east-1:{ACCOUNT_ID}:log-group:/aws/lambda/Gen3DNotifyLambda`
- **Purpose**: Logs for Notify Lambda function
- **Retention**: 30 days
- **Estimated Size**: Variable based on invocations

#### /gen3d/application
- **Type**: CloudWatch Log Group
- **ARN**: `arn:aws:logs:us-east-1:{ACCOUNT_ID}:log-group:/gen3d/application`
- **Purpose**: Custom application logs
- **Retention**: 30 days
- **Estimated Size**: Variable

### 7.2 CloudWatch Alarms (2)

#### Gen3D-ExtractLambda-HighErrors
- **Type**: CloudWatch Alarm
- **ARN**: `arn:aws:cloudwatch:us-east-1:{ACCOUNT_ID}:alarm:Gen3D-ExtractLambda-HighErrors`
- **Purpose**: Alert on high error rate in Extract Lambda
- **Metric**: AWS/Lambda Errors
- **Threshold**: > 5 errors in 10 minutes
- **Evaluation Periods**: 2
- **Actions**: SNS notification (if configured)

#### Gen3D-SageMaker-ModelLatency
- **Type**: CloudWatch Alarm
- **ARN**: `arn:aws:cloudwatch:us-east-1:{ACCOUNT_ID}:alarm:Gen3D-SageMaker-ModelLatency`
- **Purpose**: Alert on high SageMaker latency
- **Metric**: AWS/SageMaker ModelLatency
- **Threshold**: > 60000 ms (60 seconds)
- **Evaluation Periods**: 2
- **Actions**: SNS notification (if configured)

### 7.3 CloudWatch Dashboards (1)

#### Gen3D-Operations
- **Type**: CloudWatch Dashboard
- **Name**: Gen3D-Operations
- **Purpose**: Real-time operational monitoring
- **Widgets**:
  - Lambda invocation counts
  - SageMaker latency metrics
  - Error rates
  - S3 request metrics (if enabled)
- **Auto-refresh**: 1 minute

---

## 8. Resource Tags

All resources should be tagged with the following for cost tracking and organization:

```json
{
  "Project": "Gen3D",
  "Environment": "Production",
  "ManagedBy": "Terraform",
  "CostCenter": "Genesis3D",
  "Owner": "info@2112-lab.com"
}
```

---

## 9. Cost Estimates

### Monthly Cost Breakdown (Estimated)

| Service | Resource | Unit Cost | Estimated Usage | Monthly Cost |
|---------|----------|-----------|-----------------|--------------|
| SageMaker | ml.g4dn.xlarge | $0.736/hour | 730 hours | $537.28 |
| Lambda | Gen3DExtractLambda | $0.0000002/invocation | 10,000 invocations | $0.02 |
| Lambda | Gen3DNotifyLambda | $0.0000002/invocation | 10,000 invocations | $0.02 |
| S3 | Storage | $0.023/GB | 100 GB | $2.30 |
| S3 | Requests | $0.0004/1000 | 20,000 requests | $0.01 |
| ECR | Storage | $0.10/GB | 10 GB | $1.00 |
| CloudWatch | Logs | $0.50/GB | 5 GB | $2.50 |
| SES | Emails | $0.10/1000 | 10,000 emails | $1.00 |

**Total Estimated Monthly Cost**: ~$544.13

**Note**: Largest cost driver is SageMaker endpoint. Consider:
- Auto-scaling based on demand
- Spot instances for cost savings
- Scaling to zero during off-hours if applicable

---

## 10. Security Resources

### 10.1 Bucket Policies

#### gen3d-data-bucket Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::gen3d-data-bucket/public/*"
    }
  ]
}
```

### 10.2 S3 CORS Configuration

```json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

### 10.3 Lambda Resource Policies

Both Lambda functions have resource policies allowing S3 bucket to invoke them.

---

## 11. Network Resources

### VPC Configuration (Optional Enhancement)

For enhanced security, consider deploying in VPC:

- **VPC**: Create dedicated Gen3D VPC
- **Subnets**: Public and private subnets in 2 AZs
- **Security Groups**: Restrictive inbound/outbound rules
- **VPC Endpoints**: S3, SageMaker, CloudWatch, SES

**Note**: Current implementation uses default VPC/public endpoints for simplicity.

---

## 12. Backup and Recovery

### Backup Strategy

| Resource Type | Backup Method | Frequency | Retention |
|--------------|---------------|-----------|-----------|
| S3 Data | Versioning | Automatic | 90 days |
| S3 Data | Cross-region replication | Real-time | Indefinite |
| Lambda Code | Version snapshots | Per deployment | All versions |
| SageMaker Model | S3 storage | Per update | Latest 5 versions |
| Configuration | Infrastructure as Code | Per change | Git history |

---

## 13. Resource Naming Convention

All resources follow the naming pattern:

```
Gen3D{ServiceType}{Purpose}

Examples:
- Gen3DSageMakerExecutionRole
- Gen3DExtractLambda
- Gen3DSAMAsyncEndpoint
- gen3d-data-bucket (lowercase for S3)
```

---

## 14. Resource Dependencies

```
IAM Roles
    ↓
S3 Buckets
    ↓
ECR Repository → Docker Image
    ↓
SageMaker Model → Endpoint Config → Endpoint
    ↓
Lambda Functions
    ↓
S3 Event Notifications
    ↓
CloudWatch Logs & Alarms
```

---

## 15. Compliance and Governance

### AWS Config Rules (Recommended)

- S3 bucket encryption enabled
- S3 bucket versioning enabled
- Lambda functions using supported runtime
- IAM policies attached to roles
- CloudWatch log retention configured

### AWS CloudTrail

- Enable CloudTrail for all API calls
- Log to dedicated audit bucket
- Enable log file validation
- Integrate with CloudWatch Logs

---

## 16. Disaster Recovery Resources

### Required for DR

1. **Backup Bucket** (not created by default):
   - Cross-region replica of gen3d-data-bucket
   - Region: us-west-2

2. **CloudFormation Stack** (recommended):
   - Export all resources as CloudFormation
   - Store template in version control
   - Enables rapid rebuild

---

## 17. Documentation Resources

### Created Documents

1. **Gen3D - Architecture - 1.0.md**
   - Location: Project root directory
   - Purpose: Comprehensive architecture guide
   - Owner: Architecture team

2. **Gen3D - Implementation Plan - 1.0.md**
   - Location: Project root directory
   - Purpose: Step-by-step deployment guide
   - Owner: DevOps team

3. **Gen3D - AWS Resources - 1.0.md** (this document)
   - Location: Project root directory
   - Purpose: Complete resource inventory
   - Owner: Operations team

4. **Gen3D - User Guide - 1.0.md**
   - Location: Project root directory
   - Purpose: End-user documentation
   - Owner: Product team

---

## 18. Resource Limits and Quotas

### Service Limits to Monitor

| Service | Limit Type | Default | Required | Action |
|---------|-----------|---------|----------|--------|
| Lambda | Concurrent executions | 1000 | 150 | Monitor |
| SageMaker | ml.g4dn.xlarge instances | 1 | 3 | Request increase |
| SES | Sending quota (sandbox) | 200/day | Unlimited | Request production |
| S3 | Buckets per account | 100 | 2 | OK |
| CloudWatch | Custom metrics | 10,000 | <100 | OK |

---

## 19. Change Management

### Resource Modification Log

Track all changes to resources:

| Date | Resource | Change | Author | Ticket |
|------|----------|--------|--------|--------|
| YYYY-MM-DD | Gen3DSAMAsyncEndpoint | Created | DevOps | GEN3D-001 |
| YYYY-MM-DD | Gen3DExtractLambda | Updated timeout | DevOps | GEN3D-002 |

---

## 20. Decommissioning Checklist

When retiring resources:

1. Export all user data from S3
2. Delete S3 event notifications
3. Delete Lambda functions
4. Delete SageMaker endpoint (stops billing)
5. Delete SageMaker endpoint config
6. Delete SageMaker model
7. Delete ECR images and repository
8. Empty and delete S3 buckets
9. Delete CloudWatch alarms and dashboard
10. Delete IAM roles and policies
11. Remove SES verified identities
12. Delete CloudWatch log groups (after retention period)

---

## Summary

This document provides a complete inventory of all AWS resources used in the Gen3D deployment. All resources are prefixed with "Gen3D" for easy identification and cost tracking. For detailed implementation instructions, refer to the Implementation Plan document.

**Last Updated**: Initial version
**Maintained By**: DevOps Team
**Contact**: info@2112-lab.com
