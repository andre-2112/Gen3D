# Gen3D - Architecture Guide v1.0

## Executive Summary

Gen3D is a cloud-based service that leverages Meta's SAM 3D Objects foundation model to extract high-quality 3D meshes from 2D images. The service is deployed on AWS using a serverless architecture that provides scalability, reliability, and cost-effectiveness.

## System Overview

Gen3D transforms single images with object masks into complete 3D models (.ply format) containing geometry, texture, and spatial layout information. The system excels in real-world scenarios with occlusion, clutter, and challenging object poses.

### Key Capabilities

- Single-image 3D reconstruction with texture mapping
- Multi-object extraction from single images
- Asynchronous processing for scalability
- User-isolated storage with secure access controls
- Email notifications for job completion and failures
- Web-based interface for image upload and object selection

## Architecture Components

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                  (S3 Static Website - PUBLIC)                   │
│              HTML5 + JavaScript Image Upload UI                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ Upload Image + Mask
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Amazon S3 Storage                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Gen3DDataBucket                                          │  │
│  │  - /public/           (Static website)                   │  │
│  │  - /users/{user_id}/input/  (Upload trigger)            │  │
│  │  - /users/{user_id}/output/ (Completion trigger)        │  │
│  └──────────────┬───────────────────────┬───────────────────┘  │
└─────────────────┼───────────────────────┼──────────────────────┘
                  │                       │
      S3 Event    │                       │ S3 Event
      (PUT)       │                       │ (PUT)
                  ▼                       ▼
         ┌────────────────┐      ┌────────────────┐
         │ AWS Lambda     │      │ AWS Lambda     │
         │ Gen3DExtract   │      │ Gen3DNotify    │
         └────────┬───────┘      └────────┬───────┘
                  │                       │
                  │ Invoke Async          │ Send Email
                  │                       │
                  ▼                       ▼
    ┌──────────────────────────┐  ┌────────────────┐
    │   Amazon SageMaker       │  │   Amazon SES   │
    │   Async Inference        │  │   Email        │
    │   - SAM 3D Model         │  │   Notification │
    │   - GPU Instance         │  │                │
    │   - Custom Container     │  └────────────────┘
    └──────────┬───────────────┘
               │
               │ Write Output
               ▼
    ┌──────────────────────────┐
    │    S3 Output Path        │
    │ /users/{user_id}/output/ │
    └──────────────────────────┘
               │
               │
               ▼
    ┌──────────────────────────┐
    │   Amazon CloudWatch      │
    │   - Logs                 │
    │   - Metrics              │
    │   - Alarms               │
    └──────────────────────────┘
```

## Component Details

### 1. Amazon S3 Storage Layer

**Purpose**: Central storage for all system data including input images, output meshes, and web application files.

**Bucket Structure**:
```
Gen3DDataBucket/
├── public/
│   ├── index.html              # Web interface
│   ├── css/
│   ├── js/
│   └── assets/
└── users/
    └── {user_id}/
        ├── input/              # User uploads (trigger point)
        │   └── {timestamp}_{filename}
        └── output/             # Generated meshes (notification point)
            └── {timestamp}_{filename}.ply
```

**Key Features**:
- Server-side encryption (SSE-S3)
- Versioning enabled for data recovery
- Lifecycle policies for cost optimization
- Event notifications for workflow automation
- Static website hosting for public folder
- CORS configuration for browser uploads

### 2. Amazon SageMaker Inference

**Purpose**: Hosts and executes the SAM 3D Objects model for 3D reconstruction.

**Configuration**:
- **Deployment Type**: Asynchronous Inference Endpoint
- **Instance Type**: ml.g4dn.xlarge (or ml.g5.xlarge for better performance)
- **Container**: Custom Docker image with SAM 3D model
- **Model Location**: S3 path to model artifacts
- **Auto-scaling**: Based on queue depth and processing time

**Model Specifications**:
- **Framework**: PyTorch (custom inference code)
- **Input**: RGBA image (mask in alpha channel) or separate image + mask
- **Output**: 3D Gaussian splat (.ply format)
- **Processing Time**: Variable based on image complexity (~10-60 seconds)

**Async Configuration**:
```
Input S3 Path: s3://Gen3DDataBucket/users/{user_id}/input/
Output S3 Path: s3://Gen3DDataBucket/users/{user_id}/output/
Max Concurrent Invocations: 10
Max Payload Size: 100 MB
```

### 3. AWS Lambda Functions

#### 3.1 Gen3DExtractLambda

**Purpose**: Orchestrates the 3D extraction process by invoking SageMaker.

**Trigger**: S3 PUT event on `/users/*/input/*`

**Workflow**:
1. Receive S3 event notification
2. Extract user_id and file information
3. Validate input file format
4. Prepare SageMaker async invocation request
5. Invoke SageMaker endpoint
6. Log invocation details to CloudWatch
7. Handle errors and send failure notifications

**Configuration**:
- Runtime: Python 3.11
- Memory: 512 MB
- Timeout: 30 seconds
- Concurrent Executions: 100

#### 3.2 Gen3DNotifyLambda

**Purpose**: Sends email notifications when 3D mesh generation completes.

**Trigger**: S3 PUT event on `/users/*/output/*`

**Workflow**:
1. Receive S3 event notification
2. Extract user_id and output file information
3. Generate pre-signed URL for mesh download (24-hour expiry)
4. Format notification email with results
5. Send email via SES to user
6. Send copy to admin (info@2112-lab.com)
7. Log notification details

**Configuration**:
- Runtime: Python 3.11
- Memory: 256 MB
- Timeout: 15 seconds
- Concurrent Executions: 50

### 4. Amazon SES (Simple Email Service)

**Purpose**: Delivers email notifications for job completion and failures.

**Configuration**:
- Verified sender: noreply@genesis3d.com (or configured domain)
- Verified recipient: info@2112-lab.com (admin)
- User emails verified on-demand or via SES sandbox exit
- Email templates for consistent formatting

**Notification Types**:
1. **Success Notification**: Includes download link and mesh statistics
2. **Failure Notification**: Includes error details and support information
3. **Admin Alert**: System-wide issues or unusual patterns

### 5. Amazon CloudWatch

**Purpose**: Centralized logging, monitoring, and alerting.

**Log Groups**:
- `/aws/lambda/Gen3DExtractLambda`
- `/aws/lambda/Gen3DNotifyLambda`
- `/aws/sagemaker/Endpoints/Gen3DSAMEndpoint`

**Metrics**:
- Lambda invocation count and duration
- SageMaker invocation count and latency
- S3 upload/download counts
- Error rates and types

**Alarms**:
- High error rate (>5% failures)
- SageMaker endpoint health
- Lambda throttling
- S3 bucket quota warnings

### 6. IAM Security Layer

**Purpose**: Implements least-privilege access control across all services.

**Key Roles**:

#### Gen3DSageMakerExecutionRole
- Read from S3 input paths
- Write to S3 output paths
- Write logs to CloudWatch
- Pull container images from ECR

#### Gen3DLambdaExtractRole
- Read from S3 input bucket
- Invoke SageMaker async endpoint
- Write logs to CloudWatch
- Access to parameter store for configuration

#### Gen3DLambdaNotifyRole
- Read from S3 output bucket
- Send emails via SES
- Write logs to CloudWatch
- Generate S3 pre-signed URLs

## Data Flow

### Primary Processing Flow

1. **Image Upload**:
   - User accesses web interface from S3 static website
   - Selects image and draws bounding box around object
   - JavaScript generates mask and uploads both to S3
   - Files stored in `/users/{user_id}/input/`

2. **Processing Initiation**:
   - S3 triggers Gen3DExtractLambda via event notification
   - Lambda validates input and extracts metadata
   - Lambda invokes SageMaker async endpoint
   - SageMaker queues request and returns invocation ARN

3. **Model Inference**:
   - SageMaker retrieves input from S3
   - Loads SAM 3D model (cached on instance)
   - Processes image and mask to generate 3D mesh
   - Writes .ply file to S3 output path
   - Updates async invocation status

4. **Completion Notification**:
   - S3 triggers Gen3DNotifyLambda via event notification
   - Lambda generates download link
   - Sends success email to user and admin
   - Logs completion metrics

### Error Handling Flow

1. **Validation Failure**:
   - Lambda detects invalid input format
   - Sends immediate error notification via SES
   - Logs error details to CloudWatch

2. **Processing Failure**:
   - SageMaker encounters inference error
   - Writes error file to output path
   - Gen3DNotifyLambda detects error file
   - Sends failure notification with error details

3. **System Failure**:
   - CloudWatch alarm triggers on repeated failures
   - SNS notification sent to operations team
   - Admin receives detailed error report

## Security Architecture

### Data Protection

- **Encryption at Rest**: S3 SSE-S3 encryption enabled
- **Encryption in Transit**: HTTPS/TLS for all communications
- **Access Control**: IAM policies with least-privilege principle
- **User Isolation**: Path-based access controls in S3
- **Audit Logging**: CloudTrail enabled for all API calls

### Network Security

- **VPC Configuration**: SageMaker deployed in private subnet
- **Security Groups**: Restrictive inbound/outbound rules
- **Endpoint Policies**: Limit access to specific S3 buckets
- **No Public Access**: All services communicate via AWS private network

### Credential Management

- **IAM Roles**: No long-term credentials stored in code
- **Secrets Manager**: API keys and sensitive configuration
- **Parameter Store**: Non-sensitive configuration values
- **Automatic Rotation**: Credentials rotated according to policy

## Scalability Considerations

### Horizontal Scaling

- **Lambda**: Auto-scales to handle concurrent uploads
- **SageMaker**: Async queue absorbs traffic spikes
- **S3**: Unlimited scalability for storage
- **SES**: High throughput for notifications

### Performance Optimization

- **Model Caching**: SageMaker keeps model loaded in memory
- **Instance Warm-up**: Minimum capacity to avoid cold starts
- **Batch Processing**: Optional batching for cost efficiency
- **CDN Integration**: CloudFront for static website delivery

### Cost Optimization

- **Auto-scaling**: Scale down during low usage periods
- **Spot Instances**: Consider for non-critical workloads
- **S3 Lifecycle**: Move old outputs to Glacier after 90 days
- **Reserved Capacity**: For predictable baseline load

## Monitoring and Observability

### Key Performance Indicators

- **Processing Time**: Time from upload to completion
- **Success Rate**: Percentage of successful mesh generations
- **User Activity**: Upload frequency and patterns
- **Cost per Mesh**: Total AWS cost divided by mesh count

### Operational Dashboards

1. **Real-time Operations**: Current queue depth, active jobs
2. **Historical Trends**: Daily/weekly processing volumes
3. **Error Analysis**: Failure patterns and root causes
4. **Cost Tracking**: Service-level cost breakdown

## Disaster Recovery

### Backup Strategy

- **S3 Versioning**: Protects against accidental deletions
- **Cross-Region Replication**: Optional for critical data
- **Configuration Backups**: Infrastructure as Code in version control
- **Model Artifacts**: Versioned storage in S3

### Recovery Procedures

- **Data Loss**: Restore from S3 versions or backups
- **Service Outage**: Failover to standby region (if configured)
- **Corruption**: Rollback to previous model version
- **RTO**: 1 hour for service restoration
- **RPO**: Zero data loss with S3 versioning

## Future Enhancements

### Short-term (1-3 months)

- Multi-region deployment for global availability
- Real-time progress updates via WebSocket
- Batch processing for multiple objects
- Quality presets (fast/balanced/quality)

### Medium-term (3-6 months)

- Integration with SAM 3D Body for human meshes
- Advanced visualization in web interface
- User management and authentication
- API for programmatic access

### Long-term (6-12 months)

- Custom model fine-tuning per user
- Collaborative 3D editing tools
- Mobile application
- Enterprise features (team management, SSO)

## Compliance and Governance

- **Data Residency**: All data stored in specified AWS region
- **Privacy**: User data isolation enforced at storage layer
- **Audit Trail**: Complete audit log via CloudTrail
- **License Compliance**: SAM License terms enforced
- **Access Reviews**: Quarterly IAM permission audits

## Conclusion

The Gen3D architecture provides a robust, scalable, and secure platform for 3D mesh extraction from images. The serverless design minimizes operational overhead while the async processing model ensures cost-effective handling of variable workloads. With comprehensive monitoring, error handling, and security controls, the system is production-ready for real-world deployment.
