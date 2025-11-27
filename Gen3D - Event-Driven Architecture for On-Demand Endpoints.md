# Gen3D - Event-Driven Architecture for On-Demand Endpoints

## Critical Architectural Issue

**Problem Identified**: The original Option 3 (On-Demand Endpoint with Lambda Start/Stop) has a critical flaw:

### The Flawed Design:
```
1. User uploads image → S3
2. Lambda checks: Is endpoint running?
3. If NO → Start endpoint (takes 5 minutes)
4. Lambda WAITS for endpoint to be ready  ❌
5. Invoke inference
6. After 10 minutes idle → Stop endpoint
```

### Why This Fails:

- ❌ **Lambda max timeout**: 15 minutes
- ❌ **Endpoint startup**: 5 minutes (could be longer)
- ❌ **If Lambda dies/fails**, request is lost
- ❌ **Synchronous waiting** wastes Lambda time ($)
- ❌ **No retry mechanism**
- ❌ **Single point of failure**

---

## Solution Overview

Two robust event-driven solutions that eliminate the Lambda waiting problem:

1. **AWS Step Functions** (RECOMMENDED) - Orchestration service designed for long-running workflows
2. **EventBridge + DynamoDB** - Pure event-driven with queue persistence

Both solutions ensure:
- ✅ No Lambda timeout issues
- ✅ Request state is persisted
- ✅ Automatic retry on failures
- ✅ Decoupled architecture
- ✅ No lost requests

---

## 🎯 Solution 1: AWS Step Functions (RECOMMENDED)

Step Functions is **designed exactly for this use case** - orchestrating long-running workflows with waits.

### Architecture Diagram:

```
User uploads → S3 → Lambda 1 (trigger) → Step Function
                                              ↓
                                         Check endpoint status
                                              ↓
                                         If stopped → Start it
                                              ↓
                                         Wait (poll every 30s)
                                              ↓
                                         When InService → Lambda 2 (inference)
                                              ↓
                                         Lambda 3 (notify user)
```

### Benefits:

- ✅ No Lambda timeout issues (Step Functions can wait hours)
- ✅ Built-in retry logic
- ✅ Visual workflow monitoring in AWS Console
- ✅ State is persisted (survives failures)
- ✅ Can wait indefinitely for endpoint
- ✅ Cost: ~$0.025 per 1000 executions (negligible)
- ✅ Industry standard for orchestration
- ✅ Easy to debug with visual execution history

---

## Implementation: Step Functions Solution

### Step 1: Create Step Function State Machine

Save this as `gen3d-state-machine.json`:

```json
{
  "Comment": "Gen3D Inference with On-Demand Endpoint",
  "StartAt": "CheckEndpointStatus",
  "States": {
    "CheckEndpointStatus": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:sagemaker:describeEndpoint",
      "Parameters": {
        "EndpointName": "Gen3DSAMEndpoint"
      },
      "ResultPath": "$.endpointStatus",
      "Next": "IsEndpointRunning",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "NotifyFailure"
      }]
    },

    "IsEndpointRunning": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.endpointStatus.EndpointStatus",
        "StringEquals": "InService",
        "Next": "InvokeInference"
      }],
      "Default": "StartEndpoint"
    },

    "StartEndpoint": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:sagemaker:updateEndpoint",
      "Parameters": {
        "EndpointName": "Gen3DSAMEndpoint",
        "EndpointConfigName": "Gen3DSAM-Config"
      },
      "ResultPath": "$.startResult",
      "Next": "WaitForEndpoint"
    },

    "WaitForEndpoint": {
      "Type": "Wait",
      "Seconds": 30,
      "Next": "CheckEndpointStatusAgain"
    },

    "CheckEndpointStatusAgain": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:sagemaker:describeEndpoint",
      "Parameters": {
        "EndpointName": "Gen3DSAMEndpoint"
      },
      "ResultPath": "$.endpointStatus",
      "Next": "IsEndpointReadyNow"
    },

    "IsEndpointReadyNow": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.endpointStatus.EndpointStatus",
        "StringEquals": "InService",
        "Next": "InvokeInference"
      }],
      "Default": "WaitForEndpoint"
    },

    "InvokeInference": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "Gen3DInferenceLambda",
        "Payload": {
          "imageKey.$": "$.imageKey",
          "maskKey.$": "$.maskKey",
          "userId.$": "$.userId"
        }
      },
      "ResultPath": "$.inferenceResult",
      "Next": "NotifySuccess"
    },

    "NotifySuccess": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "Gen3DNotifyLambda",
        "Payload": {
          "userId.$": "$.userId",
          "status": "success",
          "outputKey.$": "$.inferenceResult.Payload.outputKey"
        }
      },
      "End": true
    },

    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "Gen3DNotifyLambda",
        "Payload": {
          "userId.$": "$.userId",
          "status": "failed",
          "error.$": "$.error"
        }
      },
      "End": true
    }
  }
}
```

---

### Step 2: Lambda 1 - Trigger Lambda (Starts Step Function)

This Lambda is triggered by S3 uploads and starts the Step Function execution.

**File**: `lambda_trigger_stepfunction.py`

```python
import boto3
import json
import time

sfn_client = boto3.client('stepfunctions')
s3_client = boto3.client('s3')

# Step Function ARN (replace with your actual ARN after creation)
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:Gen3DInferenceStateMachine'

def lambda_handler(event, context):
    """
    Triggered by S3 upload.
    Extracts metadata and starts Step Function execution.
    """

    # Parse S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    print(f"Received S3 event: {bucket}/{key}")

    # Only process image files (not masks or metadata)
    if not key.endswith('_image.png'):
        print("Skipping non-image file")
        return {'statusCode': 200, 'body': 'Skipped non-image file'}

    # Extract user ID and construct mask key
    parts = key.split('/')
    if len(parts) < 3:
        print("Invalid key format")
        return {'statusCode': 400, 'body': 'Invalid key format'}

    user_id = parts[1]
    base_name = key.replace('_image.png', '')
    mask_key = f"{base_name}_mask.png"

    # Verify mask exists
    try:
        s3_client.head_object(Bucket=bucket, Key=mask_key)
        print(f"✓ Found mask: {mask_key}")
    except:
        print(f"✗ Mask not found: {mask_key}")
        return {'statusCode': 400, 'body': 'Mask file missing'}

    # Create unique execution name
    execution_name = f"gen3d-{user_id}-{int(time.time())}"

    # Start Step Function execution
    try:
        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps({
                'imageKey': key,
                'maskKey': mask_key,
                'userId': user_id,
                'bucket': bucket
            })
        )

        print(f"✓ Started Step Function execution: {execution_name}")
        print(f"  Execution ARN: {response['executionArn']}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Inference workflow started',
                'executionArn': response['executionArn'],
                'executionName': execution_name
            })
        }

    except Exception as e:
        print(f"✗ Failed to start Step Function: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Failed to start workflow',
                'details': str(e)
            })
        }
```

**Lambda Configuration:**
```bash
# Create Lambda function
zip -j lambda_trigger.zip lambda_trigger_stepfunction.py

aws lambda create-function \
    --function-name Gen3DTriggerLambda \
    --runtime python3.11 \
    --role arn:aws:iam::ACCOUNT_ID:role/Gen3DLambdaRole \
    --handler lambda_trigger_stepfunction.lambda_handler \
    --zip-file fileb://lambda_trigger.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={
        STATE_MACHINE_ARN=arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:Gen3DInferenceStateMachine
    }"

# Update IAM role to allow Step Functions execution
aws iam attach-role-policy \
    --role-name Gen3DLambdaRole \
    --policy-arn arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess
```

---

### Step 3: Lambda 2 - Inference Lambda

This Lambda performs the actual inference and is called by Step Functions when the endpoint is ready.

**File**: `lambda_inference.py`

```python
import boto3
import json
from PIL import Image
import io
import base64

s3_client = boto3.client('s3')
sagemaker_runtime = boto3.client('sagemaker-runtime')

ENDPOINT_NAME = 'Gen3DSAMEndpoint'

def lambda_handler(event, context):
    """
    Performs actual inference.
    Called by Step Function when endpoint is ready.
    """

    image_key = event['imageKey']
    mask_key = event['maskKey']
    user_id = event['userId']
    bucket = event['bucket']

    print(f"Starting inference for user {user_id}")
    print(f"  Image: {image_key}")
    print(f"  Mask: {mask_key}")

    try:
        # Download image and mask from S3
        print("Downloading image and mask from S3...")
        image_obj = s3_client.get_object(Bucket=bucket, Key=image_key)
        mask_obj = s3_client.get_object(Bucket=bucket, Key=mask_key)

        image_data = image_obj['Body'].read()
        mask_data = mask_obj['Body'].read()

        # Prepare payload for SageMaker
        payload = {
            'image': base64.b64encode(image_data).decode('utf-8'),
            'mask': base64.b64encode(mask_data).decode('utf-8')
        }

        print(f"Invoking SageMaker endpoint: {ENDPOINT_NAME}")

        # Invoke SageMaker endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType='application/json',
            Body=json.dumps(payload)
        )

        # Read response
        result = response['Body'].read()

        # Save output to S3
        output_key = image_key.replace('/input/', '/output/').replace('_image.png', '.ply')

        print(f"Saving output to S3: {output_key}")
        s3_client.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=result,
            ContentType='application/octet-stream'
        )

        print("✓ Inference completed successfully")

        return {
            'statusCode': 200,
            'outputKey': output_key,
            'message': 'Inference completed successfully'
        }

    except Exception as e:
        print(f"✗ Inference error: {str(e)}")

        # Create error file in S3
        error_key = image_key.replace('/input/', '/output/').replace('_image.png', '_error.json')
        s3_client.put_object(
            Bucket=bucket,
            Key=error_key,
            Body=json.dumps({
                'error': str(e),
                'imageKey': image_key,
                'maskKey': mask_key,
                'userId': user_id
            }),
            ContentType='application/json'
        )

        # Re-raise exception so Step Function catches it
        raise
```

**Lambda Configuration:**
```bash
# Create Lambda function
zip -j lambda_inference.zip lambda_inference.py

aws lambda create-function \
    --function-name Gen3DInferenceLambda \
    --runtime python3.11 \
    --role arn:aws:iam::ACCOUNT_ID:role/Gen3DLambdaRole \
    --handler lambda_inference.lambda_handler \
    --zip-file fileb://lambda_inference.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment "Variables={
        ENDPOINT_NAME=Gen3DSAMEndpoint
    }"
```

---

### Step 4: Deploy Step Functions State Machine

```bash
# Create IAM role for Step Functions
cat > /tmp/stepfunctions-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "states.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
    --role-name Gen3DStepFunctionsRole \
    --assume-role-policy-document file:///tmp/stepfunctions-trust-policy.json

# Create policy for Step Functions
cat > /tmp/stepfunctions-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:*:*:function:Gen3DInferenceLambda",
        "arn:aws:lambda:*:*:function:Gen3DNotifyLambda"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sagemaker:DescribeEndpoint",
        "sagemaker:UpdateEndpoint"
      ],
      "Resource": "arn:aws:sagemaker:*:*:endpoint/gen3dsamendpoint"
    }
  ]
}
EOF

aws iam put-role-policy \
    --role-name Gen3DStepFunctionsRole \
    --policy-name Gen3DStepFunctionsPolicy \
    --policy-document file:///tmp/stepfunctions-policy.json

# Create state machine
aws stepfunctions create-state-machine \
    --name Gen3DInferenceStateMachine \
    --definition file://gen3d-state-machine.json \
    --role-arn arn:aws:iam::ACCOUNT_ID:role/Gen3DStepFunctionsRole \
    --type STANDARD

# Get the ARN (use this in Lambda 1 environment variable)
aws stepfunctions list-state-machines --query "stateMachines[?name=='Gen3DInferenceStateMachine'].stateMachineArn" --output text
```

---

### Step 5: Update S3 Event Notification

Update the S3 bucket to trigger the new Lambda:

```bash
# Remove old trigger (if exists)
aws s3api put-bucket-notification-configuration \
    --bucket gen3d-data-bucket \
    --notification-configuration '{}'

# Add Lambda permission
aws lambda add-permission \
    --function-name Gen3DTriggerLambda \
    --statement-id AllowS3Invoke \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::gen3d-data-bucket

# Configure S3 notification
cat > /tmp/s3-notification.json << 'EOF'
{
  "LambdaFunctionConfigurations": [{
    "Id": "Gen3DTrigger",
    "LambdaFunctionArn": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:Gen3DTriggerLambda",
    "Events": ["s3:ObjectCreated:*"],
    "Filter": {
      "Key": {
        "FilterRules": [
          {"Name": "prefix", "Value": "users/"},
          {"Name": "suffix", "Value": "_image.png"}
        ]
      }
    }
  }]
}
EOF

aws s3api put-bucket-notification-configuration \
    --bucket gen3d-data-bucket \
    --notification-configuration file:///tmp/s3-notification.json
```

---

### Step 6: Monitoring and Testing

**View Step Function Executions in Console:**
```
AWS Console → Step Functions → State machines → Gen3DInferenceStateMachine
→ Click on any execution to see visual workflow
```

**Test the workflow:**
```bash
# Upload test image and mask
aws s3 cp test_image.png s3://gen3d-data-bucket/users/test123/input/12345_object_1_image.png
aws s3 cp test_mask.png s3://gen3d-data-bucket/users/test123/input/12345_object_1_mask.png

# Watch Step Function execution
aws stepfunctions list-executions \
    --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:Gen3DInferenceStateMachine \
    --max-results 1

# Get execution details
aws stepfunctions describe-execution \
    --execution-arn <EXECUTION_ARN>
```

---

## 🎯 Solution 2: EventBridge + DynamoDB (Alternative)

If you prefer a more AWS-native event-driven approach without Step Functions polling.

### Architecture Diagram:

```
User uploads → S3 → Lambda 1 (trigger)
                         ↓
                    - Start endpoint
                    - Store payload in DynamoDB
                    - Return immediately

CloudWatch Events → Detects endpoint status change to "InService"
                         ↓
                    EventBridge Rule triggers Lambda 2
                         ↓
                    Lambda 2:
                    - Query DynamoDB for pending requests
                    - Process all pending inferences
                    - Delete from DynamoDB when done
```

### Benefits:

- ✅ Fully event-driven (no polling)
- ✅ No Lambda waiting
- ✅ Scales automatically
- ✅ DynamoDB stores request queue
- ✅ CloudWatch Events natively detect endpoint state changes
- ✅ Can batch process multiple requests when endpoint starts

---

## Implementation: EventBridge + DynamoDB Solution

### Step 1: Create DynamoDB Table

```bash
aws dynamodb create-table \
    --table-name Gen3DInferenceQueue \
    --attribute-definitions \
        AttributeName=requestId,AttributeType=S \
    --key-schema \
        AttributeName=requestId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --tags Key=Project,Value=Gen3D

# Add GSI for status queries
aws dynamodb update-table \
    --table-name Gen3DInferenceQueue \
    --attribute-definitions \
        AttributeName=status,AttributeType=S \
        AttributeName=timestamp,AttributeType=N \
    --global-secondary-index-updates '[
        {
            "Create": {
                "IndexName": "status-timestamp-index",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"}
                ],
                "Projection": {"ProjectionType": "ALL"}
            }
        }
    ]'
```

---

### Step 2: Lambda 1 - Queue Request and Start Endpoint

**File**: `lambda_queue_request.py`

```python
import boto3
import json
import time
import uuid

s3_client = boto3.client('s3')
sagemaker_client = boto3.client('sagemaker')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Gen3DInferenceQueue')

ENDPOINT_NAME = 'Gen3DSAMEndpoint'

def lambda_handler(event, context):
    """
    Start endpoint (if needed) and queue request in DynamoDB.
    Returns immediately without waiting.
    """

    # Parse S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    if not key.endswith('_image.png'):
        return {'statusCode': 200, 'body': 'Skipped'}

    # Extract metadata
    parts = key.split('/')
    user_id = parts[1]
    mask_key = key.replace('_image.png', '_mask.png')

    # Verify mask exists
    try:
        s3_client.head_object(Bucket=bucket, Key=mask_key)
    except:
        print(f"✗ Mask not found: {mask_key}")
        return {'statusCode': 400, 'body': 'Mask missing'}

    # Check endpoint status
    try:
        response = sagemaker_client.describe_endpoint(EndpointName=ENDPOINT_NAME)
        endpoint_status = response['EndpointStatus']
        print(f"Endpoint status: {endpoint_status}")
    except Exception as e:
        print(f"Endpoint not found: {e}")
        endpoint_status = 'NotFound'

    # If not running, start it
    if endpoint_status != 'InService':
        print("⚠️ Endpoint not ready. Starting endpoint...")
        try:
            sagemaker_client.update_endpoint(
                EndpointName=ENDPOINT_NAME,
                EndpointConfigName='Gen3DSAM-Config'
            )
            print("✓ Endpoint start initiated")
        except Exception as e:
            print(f"✗ Failed to start endpoint: {e}")
            # Continue anyway - maybe it's already starting

    # Generate request ID
    request_id = f"{user_id}-{int(time.time()*1000)}-{str(uuid.uuid4())[:8]}"

    # Store request in DynamoDB queue
    try:
        table.put_item(
            Item={
                'requestId': request_id,
                'userId': user_id,
                'imageKey': key,
                'maskKey': mask_key,
                'bucket': bucket,
                'status': 'pending',
                'timestamp': int(time.time()),
                'createdAt': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        )
        print(f"✓ Queued request: {request_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Request queued. Will process when endpoint is ready.',
                'requestId': request_id
            })
        }

    except Exception as e:
        print(f"✗ Failed to queue request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

---

### Step 3: Create EventBridge Rule for Endpoint State Changes

```bash
# Create EventBridge rule that triggers when endpoint becomes InService
aws events put-rule \
    --name Gen3D-EndpointReady \
    --description "Trigger when SageMaker endpoint becomes InService" \
    --event-pattern '{
      "source": ["aws.sagemaker"],
      "detail-type": ["SageMaker Endpoint State Change"],
      "detail": {
        "EndpointName": ["Gen3DSAMEndpoint"],
        "EndpointStatus": ["InService"]
      }
    }'

# Add Lambda as target
aws events put-targets \
    --rule Gen3D-EndpointReady \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT_ID:function:Gen3DProcessQueueLambda"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
    --function-name Gen3DProcessQueueLambda \
    --statement-id AllowEventBridge \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/Gen3D-EndpointReady
```

---

### Step 4: Lambda 2 - Process Queue When Endpoint Ready

**File**: `lambda_process_queue.py`

```python
import boto3
import json
import base64

s3_client = boto3.client('s3')
sagemaker_runtime = boto3.client('sagemaker-runtime')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Gen3DInferenceQueue')

ENDPOINT_NAME = 'Gen3DSAMEndpoint'

def lambda_handler(event, context):
    """
    Triggered when endpoint becomes InService.
    Process all pending requests from DynamoDB queue.
    """

    print("🚀 Endpoint is ready! Processing queued requests...")
    print(f"Event: {json.dumps(event)}")

    # Query for pending requests
    try:
        response = table.query(
            IndexName='status-timestamp-index',
            KeyConditionExpression='#status = :pending',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':pending': 'pending'}
        )

        requests = response['Items']
        print(f"📋 Found {len(requests)} pending requests")

    except Exception as e:
        print(f"✗ Failed to query DynamoDB: {e}")
        return {'statusCode': 500, 'error': str(e)}

    # Process each request
    processed = 0
    failed = 0

    for req in requests:
        request_id = req['requestId']
        print(f"\n🔄 Processing {request_id}...")

        try:
            # Download image and mask
            image_obj = s3_client.get_object(Bucket=req['bucket'], Key=req['imageKey'])
            mask_obj = s3_client.get_object(Bucket=req['bucket'], Key=req['maskKey'])

            image_data = image_obj['Body'].read()
            mask_data = mask_obj['Body'].read()

            # Prepare payload
            payload = {
                'image': base64.b64encode(image_data).decode('utf-8'),
                'mask': base64.b64encode(mask_data).decode('utf-8')
            }

            # Invoke SageMaker
            print(f"  Invoking SageMaker endpoint...")
            inference_response = sagemaker_runtime.invoke_endpoint(
                EndpointName=ENDPOINT_NAME,
                ContentType='application/json',
                Body=json.dumps(payload)
            )

            # Save output
            output_key = req['imageKey'].replace('/input/', '/output/').replace('_image.png', '.ply')
            s3_client.put_object(
                Bucket=req['bucket'],
                Key=output_key,
                Body=inference_response['Body'].read(),
                ContentType='application/octet-stream'
            )

            # Update DynamoDB to completed
            table.update_item(
                Key={'requestId': request_id},
                UpdateExpression='SET #status = :completed, outputKey = :output, completedAt = :time',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':completed': 'completed',
                    ':output': output_key,
                    ':time': int(time.time())
                }
            )

            print(f"  ✓ Completed: {output_key}")
            processed += 1

            # TODO: Trigger notification Lambda
            # boto3.client('lambda').invoke(
            #     FunctionName='Gen3DNotifyLambda',
            #     InvocationType='Event',
            #     Payload=json.dumps({'userId': req['userId'], 'status': 'success', 'outputKey': output_key})
            # )

        except Exception as e:
            print(f"  ✗ Failed: {str(e)}")
            failed += 1

            # Update status to failed
            try:
                table.update_item(
                    Key={'requestId': request_id},
                    UpdateExpression='SET #status = :failed, errorMessage = :error, failedAt = :time',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':failed': 'failed',
                        ':error': str(e),
                        ':time': int(time.time())
                    }
                )

                # Create error file
                error_key = req['imageKey'].replace('/input/', '/output/').replace('_image.png', '_error.json')
                s3_client.put_object(
                    Bucket=req['bucket'],
                    Key=error_key,
                    Body=json.dumps({'error': str(e), 'requestId': request_id}),
                    ContentType='application/json'
                )

            except Exception as update_error:
                print(f"  ✗ Failed to update error status: {update_error}")

    print(f"\n✅ Summary: {processed} succeeded, {failed} failed")

    return {
        'statusCode': 200,
        'processed': processed,
        'failed': failed,
        'total': len(requests)
    }
```

**Lambda Configuration:**
```bash
# Create Lambda function
zip -j lambda_process_queue.zip lambda_process_queue.py

aws lambda create-function \
    --function-name Gen3DProcessQueueLambda \
    --runtime python3.11 \
    --role arn:aws:iam::ACCOUNT_ID:role/Gen3DLambdaRole \
    --handler lambda_process_queue.lambda_handler \
    --zip-file fileb://lambda_process_queue.zip \
    --timeout 900 \
    --memory-size 1024 \
    --environment "Variables={
        ENDPOINT_NAME=Gen3DSAMEndpoint,
        QUEUE_TABLE=Gen3DInferenceQueue
    }"

# Update IAM role for DynamoDB access
aws iam attach-role-policy \
    --role-name Gen3DLambdaRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
```

---

### Step 5: Optional - Cleanup Old Requests

Create a scheduled Lambda to clean up old completed/failed requests:

```python
# lambda_cleanup_queue.py
import boto3
import time

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Gen3DInferenceQueue')

# Delete requests older than 7 days
RETENTION_DAYS = 7
CUTOFF_TIMESTAMP = int(time.time()) - (RETENTION_DAYS * 86400)

def lambda_handler(event, context):
    """Delete old requests from DynamoDB"""

    # Scan for old completed/failed requests
    response = table.scan(
        FilterExpression='#ts < :cutoff AND (#status = :completed OR #status = :failed)',
        ExpressionAttributeNames={'#ts': 'timestamp', '#status': 'status'},
        ExpressionAttributeValues={
            ':cutoff': CUTOFF_TIMESTAMP,
            ':completed': 'completed',
            ':failed': 'failed'
        }
    )

    deleted = 0
    for item in response['Items']:
        table.delete_item(Key={'requestId': item['requestId']})
        deleted += 1

    print(f"Deleted {deleted} old requests")
    return {'deleted': deleted}
```

```bash
# Schedule cleanup to run daily
aws events put-rule \
    --name Gen3D-DailyCleanup \
    --schedule-expression "rate(1 day)"

aws events put-targets \
    --rule Gen3D-DailyCleanup \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT_ID:function:Gen3DCleanupQueueLambda"
```

---

## 📊 Comparison of Solutions

| Feature | Step Functions | EventBridge + DynamoDB |
|---------|---------------|------------------------|
| **Complexity** | Medium | Medium |
| **Visual Monitoring** | ✅ Yes (console) | ❌ No (logs only) |
| **Retry Logic** | ✅ Built-in | ❌ Manual |
| **State Persistence** | ✅ Automatic | ✅ DynamoDB |
| **Cost** | $0.025/1000 executions | DynamoDB: ~$0.01/request |
| **Debugging** | ✅ Easy (visual workflow) | ❌ Harder (CloudWatch logs) |
| **Lambda Timeout Risk** | ✅ No risk | ✅ No risk |
| **Event-Driven** | ⚠️ Polling (every 30s) | ✅ Pure events (no polling) |
| **Batch Processing** | ❌ One at a time | ✅ Can batch multiple |
| **Best For** | Complex workflows | Simple queue processing |
| **Learning Curve** | Medium | Low (if familiar with AWS) |
| **Operational Overhead** | Low | Medium (manage DynamoDB) |
| **Scalability** | ✅ Excellent | ✅ Excellent |

---

## 💰 Cost Comparison

### Step Functions Approach:
```
100 requests/month:
- Step Functions: 100 executions × $0.000025 = $0.003
- Lambda executions: Same as before
- Total additional cost: ~$0.003/month (negligible)
```

### EventBridge + DynamoDB Approach:
```
100 requests/month:
- EventBridge: Free (included)
- DynamoDB writes: 100 × $0.00000125 = $0.000125
- DynamoDB reads: 100 × $0.00000025 = $0.000025
- DynamoDB storage: 100 items × 1KB × $0.25/GB = $0.000025
- Total additional cost: ~$0.002/month (negligible)
```

**Both solutions add < $0.01/month in cost** - essentially free.

---

## 🎯 Recommendation

### Use **Step Functions (Solution 1)** if:

- ✅ You want visual workflow monitoring
- ✅ You prefer AWS-managed state persistence
- ✅ You want built-in retry/error handling
- ✅ You're building complex workflows
- ✅ You value ease of debugging

### Use **EventBridge + DynamoDB (Solution 2)** if:

- ✅ You prefer pure event-driven (no polling)
- ✅ You want to batch process multiple requests
- ✅ You need fine-grained control over queue management
- ✅ You're already using DynamoDB extensively
- ✅ You want to minimize AWS service dependencies

---

## 🚀 Migration Path

To migrate from the current flawed design to Step Functions:

1. **Create Step Function** (10 minutes)
2. **Deploy Lambda functions** (10 minutes)
3. **Update S3 trigger** to point to new Lambda (5 minutes)
4. **Test with sample upload** (5 minutes)
5. **Monitor first real requests** in Step Functions console

**Total migration time: ~30 minutes**

---

## 📈 Additional Benefits

### With Either Solution:

1. **Request Tracking**: Every request has a unique ID and full history
2. **Failure Recovery**: Automatic retries on transient failures
3. **Monitoring**: CloudWatch metrics for success/failure rates
4. **Cost Efficiency**: Pay only for execution time, not waiting time
5. **Scalability**: Handles 1 request/month or 10,000/month equally well
6. **User Experience**: Reliable processing with proper error notifications

---

## 🔧 Next Steps

**Recommendation**: Implement **Step Functions Solution** for robust, production-ready architecture.

Would you like me to:
1. Update the Cost Analysis document to replace Option 3 with Step Functions approach?
2. Update the Implementation Plan v1.1 with Step Functions deployment steps?
3. Create deployment scripts to automate the entire setup?

---

**Document Version**: 1.0
**Date**: 2025-11-27
**Status**: Ready for Implementation ✅
