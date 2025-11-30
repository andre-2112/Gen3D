# Gen3D - AWS Resources v1.1

## Complete List of AWS Resources

This document provides a comprehensive, authoritative list of all AWS resources created for the Gen3D service deployment.

## Version History

- **v1.1** (2025-11-27): Minor updates for Implementation Plan v1.1 compatibility
- **v1.0** (2025-11-27): Initial release

## Changes in v1.1

- No new AWS resources added
- Updated Lambda function code (error handling improvements)
- Updated Docker container structure
- All resource specifications remain the same

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
| Secrets Manager | 1 Secret | HuggingFace token storage |

**Total Resource Count**: 21 AWS resources

---

*For complete resource details, see Gen3D - AWS Resources - 1.0.md*
*The resource list remains unchanged; only implementation code has been updated.*
