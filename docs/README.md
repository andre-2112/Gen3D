# Gen3D - AWS Deployment for SAM 3D Objects

## Overview

Gen3D is a cloud-based service that leverages Meta's SAM 3D Objects foundation model to extract high-quality 3D meshes from 2D images. This repository contains complete documentation for deploying the service on AWS.

## Documentation

This repository includes four comprehensive documents:

### 1. Architecture Guide
**File**: `Gen3D - Architecture - 1.0.md`

Complete system architecture including:
- High-level component overview
- AWS service integration
- Data flow diagrams
- Security architecture
- Scalability considerations
- Disaster recovery planning

### 2. Implementation Plan
**File**: `Gen3D - Implementation Plan - 1.0.md`

Step-by-step deployment guide with:
- All AWS CLI commands
- Lambda function code
- Docker container setup
- SageMaker configuration
- Complete web interface code
- Testing procedures
- Troubleshooting guide

### 3. AWS Resources List
**File**: `Gen3D - AWS Resources - 1.0.md`

Comprehensive resource inventory:
- All 20 AWS resources with specifications
- Cost estimates (~$544/month)
- Resource dependencies
- Security configurations
- Backup strategies

### 4. User Guide
**File**: `Gen3D - User Guide - 1.0.md`

End-user documentation:
- Getting started guide
- Web interface instructions
- Best practices for photography
- Software recommendations
- Troubleshooting and FAQ
- API usage examples

## Technology Stack

- **AWS Services**: S3, SageMaker, Lambda, SES, CloudWatch, IAM, ECR
- **ML Model**: Meta SAM 3D Objects
- **Runtime**: Python 3.11, PyTorch
- **Infrastructure**: Serverless architecture with GPU inference

## Key Features

- **Async Processing**: Scalable queue-based inference
- **Email Notifications**: Automatic alerts on completion
- **Web Interface**: HTML5 drag-and-drop interface
- **User Isolation**: Secure per-user storage
- **Monitoring**: CloudWatch logs and alarms
- **Cost-Effective**: Pay-per-use serverless design

## Quick Start

1. Review the Architecture Guide to understand the system
2. Follow the Implementation Plan for step-by-step deployment
3. Refer to AWS Resources List for resource details
4. Share the User Guide with end users

## Prerequisites

- AWS Account (Genesis3D)
- AWS CLI v2.x configured
- Docker installed
- Python 3.11+
- HuggingFace account with SAM 3D access

## Deployment

Detailed deployment instructions are in the Implementation Plan document. High-level steps:

1. Create IAM roles and policies
2. Set up S3 buckets
3. Build and deploy SageMaker model
4. Deploy Lambda functions
5. Configure SES for notifications
6. Set up CloudWatch monitoring
7. Deploy web interface
8. Test end-to-end workflow

## Architecture Overview

```
User → Web Interface (S3) → Upload Image
    ↓
S3 Event → Lambda (Extract) → SageMaker Async Endpoint
    ↓
SAM 3D Model Processing (GPU)
    ↓
Output to S3 → Lambda (Notify) → Email (SES)
```

## Cost Estimate

Monthly operational cost: ~$544
- SageMaker GPU instance: $537/month
- Lambda functions: <$1/month
- S3 storage: ~$3/month
- Other services: ~$3/month

## Support

For questions or issues:
- Email: info@2112-lab.com
- Review troubleshooting sections in documentation

## License

This documentation is provided for the Gen3D project deployment. The SAM 3D model is subject to Meta's SAM License.

## Version

- **Documentation Version**: 1.0
- **Last Updated**: Initial release
- **Maintained By**: Genesis3D Team

## References

- [SAM 3D GitHub](https://github.com/facebookresearch/sam-3d-objects)
- [SAM 3D HuggingFace](https://huggingface.co/facebook/sam-3d-objects)
- [ArXiv Paper](https://arxiv.org/abs/2511.16624)
