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

## 🎯 Solution 3: EventBridge + S3 (Most Elegant)

The simplest and most cost-effective solution: use S3 itself as the queue storage.

### Key Insight

**All our data is already in S3** (images, masks, outputs). Why introduce a separate database (DynamoDB) for queue management when we can use S3 as both data store AND queue?

### Architecture Diagram:

```
User uploads → S3 → Lambda 1 (trigger)
                         ↓
                    - Start endpoint (if needed)
                    - Create pending request JSON in S3
                    - Return immediately

CloudWatch Events → Detects endpoint status change to "InService"
                         ↓
                    EventBridge Rule triggers Lambda 2
                         ↓
                    Lambda 2:
                    - List all pending/*.json files in S3
                    - For each: Move to processing/ folder
                    - Process inference
                    - Move to completed/ or failed/ folder
```

### S3 Bucket Structure:

```
s3://gen3d-data-bucket/
├── users/
│   └── {userId}/
│       ├── input/
│       │   ├── {timestamp}_image.png
│       │   └── {timestamp}_mask.png
│       ├── output/
│       │   ├── {timestamp}.ply
│       │   └── {timestamp}_error.json (if failed)
│       └── queue/
│           ├── pending/
│           │   └── {requestId}.json
│           ├── processing/
│           │   └── {requestId}.json
│           ├── completed/
│           │   └── {requestId}.json
│           └── failed/
│               └── {requestId}.json
```

### Request JSON Format:

```json
{
  "requestId": "user123-1234567890-abc123",
  "userId": "user123",
  "imageKey": "users/user123/input/1234567890_image.png",
  "maskKey": "users/user123/input/1234567890_mask.png",
  "bucket": "gen3d-data-bucket",
  "status": "pending",
  "createdAt": "2025-11-27T10:30:00Z",
  "timestamp": 1234567890
}
```

### Benefits:

- ✅ **Simplest architecture** - no additional database service
- ✅ **Lowest cost** - S3 is ~20x cheaper than DynamoDB
- ✅ **Natural organization** - request metadata lives with the data
- ✅ **Easy debugging** - just browse S3 folders to see queue status
- ✅ **No capacity planning** - S3 auto-scales infinitely
- ✅ **Visual inspection** - see queue state directly in S3 console
- ✅ **Atomic operations** - copy+delete prevents race conditions
- ✅ **Built-in lifecycle** - use S3 lifecycle policies for cleanup
- ✅ **Audit trail** - completed/failed requests preserved automatically

---

## Implementation: EventBridge + S3 Solution

### Step 1: Lambda 1 - Queue Request in S3

**File**: `lambda_queue_s3.py`

```python
import boto3
import json
import time
import uuid

s3_client = boto3.client('s3')
sagemaker_client = boto3.client('sagemaker')

ENDPOINT_NAME = 'Gen3DSAMEndpoint'
DATA_BUCKET = 'gen3d-data-bucket'

def lambda_handler(event, context):
    """
    Start endpoint (if needed) and queue request as JSON file in S3.
    Returns immediately without waiting.
    """

    # Parse S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    print(f"Received upload: {bucket}/{key}")

    if not key.endswith('_image.png'):
        print("Skipping non-image file")
        return {'statusCode': 200, 'body': 'Skipped'}

    # Extract metadata
    # Expected format: users/{userId}/input/{timestamp}_image.png
    parts = key.split('/')
    if len(parts) < 4 or parts[0] != 'users' or parts[2] != 'input':
        print("Invalid key format")
        return {'statusCode': 400, 'body': 'Invalid path'}

    user_id = parts[1]
    filename = parts[3]
    base_name = filename.replace('_image.png', '')
    mask_key = f"users/{user_id}/input/{base_name}_mask.png"

    # Verify mask exists
    try:
        s3_client.head_object(Bucket=bucket, Key=mask_key)
        print(f"✓ Found mask: {mask_key}")
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
            print(f"⚠️ Start endpoint error (may already be starting): {e}")

    # Generate request ID
    timestamp = int(time.time())
    request_id = f"{user_id}-{timestamp}-{str(uuid.uuid4())[:8]}"

    # Create request metadata JSON
    request_data = {
        'requestId': request_id,
        'userId': user_id,
        'imageKey': key,
        'maskKey': mask_key,
        'bucket': bucket,
        'status': 'pending',
        'createdAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'timestamp': timestamp
    }

    # Save request to S3 queue (pending folder)
    queue_key = f"users/{user_id}/queue/pending/{request_id}.json"

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=queue_key,
            Body=json.dumps(request_data, indent=2),
            ContentType='application/json',
            Metadata={
                'request-id': request_id,
                'user-id': user_id,
                'status': 'pending'
            }
        )
        print(f"✓ Queued request: {queue_key}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Request queued. Will process when endpoint is ready.',
                'requestId': request_id,
                'queueKey': queue_key
            })
        }

    except Exception as e:
        print(f"✗ Failed to queue request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

**Lambda Configuration:**
```bash
# Create Lambda function
zip -j lambda_queue_s3.zip lambda_queue_s3.py

aws lambda create-function \
    --function-name Gen3DQueueS3Lambda \
    --runtime python3.11 \
    --role arn:aws:iam::ACCOUNT_ID:role/Gen3DLambdaRole \
    --handler lambda_queue_s3.lambda_handler \
    --zip-file fileb://lambda_queue_s3.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={
        ENDPOINT_NAME=Gen3DSAMEndpoint,
        DATA_BUCKET=gen3d-data-bucket
    }"
```

---

### Step 2: Create EventBridge Rule

```bash
# Create EventBridge rule that triggers when endpoint becomes InService
aws events put-rule \
    --name Gen3D-EndpointReady-S3 \
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
    --rule Gen3D-EndpointReady-S3 \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT_ID:function:Gen3DProcessS3QueueLambda"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
    --function-name Gen3DProcessS3QueueLambda \
    --statement-id AllowEventBridgeS3 \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/Gen3D-EndpointReady-S3
```

---

### Step 3: Lambda 2 - Process S3 Queue

**File**: `lambda_process_s3_queue.py`

```python
import boto3
import json
import base64
import time

s3_client = boto3.client('s3')
sagemaker_runtime = boto3.client('sagemaker-runtime')
lambda_client = boto3.client('lambda')

ENDPOINT_NAME = 'Gen3DSAMEndpoint'
DATA_BUCKET = 'gen3d-data-bucket'

def lambda_handler(event, context):
    """
    Triggered when endpoint becomes InService.
    Process all pending requests from S3 queue.
    """

    print("🚀 Endpoint is ready! Processing S3 queue...")
    print(f"Event: {json.dumps(event)}")

    # List all pending request files across all users
    pending_requests = []

    try:
        # List all pending/*.json files
        # Using prefix to scan all users
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=DATA_BUCKET,
            Prefix='users/'
        )

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                # Check if this is a pending request file
                if '/queue/pending/' in key and key.endswith('.json'):
                    pending_requests.append(key)

        print(f"📋 Found {len(pending_requests)} pending requests")

    except Exception as e:
        print(f"✗ Failed to list pending requests: {e}")
        return {'statusCode': 500, 'error': str(e)}

    # Process each request
    processed = 0
    failed = 0

    for request_key in pending_requests:
        print(f"\n🔄 Processing {request_key}...")

        try:
            # ATOMIC OPERATION: Move from pending/ to processing/
            # This prevents race conditions if multiple Lambdas run concurrently

            processing_key = request_key.replace('/queue/pending/', '/queue/processing/')

            # Step 1: Copy to processing/
            s3_client.copy_object(
                Bucket=DATA_BUCKET,
                CopySource={'Bucket': DATA_BUCKET, 'Key': request_key},
                Key=processing_key
            )

            # Step 2: Delete from pending/ (if this fails, someone else got it)
            try:
                s3_client.delete_object(Bucket=DATA_BUCKET, Key=request_key)
                print(f"  ✓ Moved to processing")
            except Exception as delete_error:
                print(f"  ⚠️ Could not delete pending (already processed?): {delete_error}")
                # Someone else is processing this - skip it
                s3_client.delete_object(Bucket=DATA_BUCKET, Key=processing_key)
                continue

            # Read request metadata
            response = s3_client.get_object(Bucket=DATA_BUCKET, Key=processing_key)
            request_data = json.loads(response['Body'].read())

            # Download image and mask
            image_obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=request_data['imageKey'])
            mask_obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=request_data['maskKey'])

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

            # Save output PLY
            output_key = request_data['imageKey'].replace('/input/', '/output/').replace('_image.png', '.ply')
            s3_client.put_object(
                Bucket=DATA_BUCKET,
                Key=output_key,
                Body=inference_response['Body'].read(),
                ContentType='application/octet-stream'
            )

            # Update request metadata
            request_data['status'] = 'completed'
            request_data['completedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            request_data['outputKey'] = output_key

            # Move to completed/ folder
            completed_key = processing_key.replace('/queue/processing/', '/queue/completed/')
            s3_client.put_object(
                Bucket=DATA_BUCKET,
                Key=completed_key,
                Body=json.dumps(request_data, indent=2),
                ContentType='application/json'
            )

            # Delete from processing/
            s3_client.delete_object(Bucket=DATA_BUCKET, Key=processing_key)

            print(f"  ✓ Completed: {output_key}")
            processed += 1

            # Trigger notification Lambda (asynchronously)
            try:
                lambda_client.invoke(
                    FunctionName='Gen3DNotifyLambda',
                    InvocationType='Event',
                    Payload=json.dumps({
                        'userId': request_data['userId'],
                        'status': 'success',
                        'outputKey': output_key,
                        'requestId': request_data['requestId']
                    })
                )
            except Exception as notify_error:
                print(f"  ⚠️ Notification failed: {notify_error}")

        except Exception as e:
            print(f"  ✗ Failed: {str(e)}")
            failed += 1

            # Move to failed/ folder with error details
            try:
                # Read request data (if we got that far)
                try:
                    response = s3_client.get_object(Bucket=DATA_BUCKET, Key=processing_key)
                    request_data = json.loads(response['Body'].read())
                except:
                    # If we couldn't move to processing, read from pending
                    response = s3_client.get_object(Bucket=DATA_BUCKET, Key=request_key)
                    request_data = json.loads(response['Body'].read())

                request_data['status'] = 'failed'
                request_data['failedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                request_data['error'] = str(e)

                # Save to failed/ folder
                failed_key = request_key.replace('/queue/pending/', '/queue/failed/')
                if '/queue/processing/' in request_key:
                    failed_key = request_key.replace('/queue/processing/', '/queue/failed/')

                s3_client.put_object(
                    Bucket=DATA_BUCKET,
                    Key=failed_key,
                    Body=json.dumps(request_data, indent=2),
                    ContentType='application/json'
                )

                # Clean up
                try:
                    s3_client.delete_object(Bucket=DATA_BUCKET, Key=request_key)
                except:
                    pass
                try:
                    s3_client.delete_object(Bucket=DATA_BUCKET, Key=processing_key)
                except:
                    pass

                # Create error file in output folder
                error_key = request_data['imageKey'].replace('/input/', '/output/').replace('_image.png', '_error.json')
                s3_client.put_object(
                    Bucket=DATA_BUCKET,
                    Key=error_key,
                    Body=json.dumps({
                        'error': str(e),
                        'requestId': request_data['requestId'],
                        'timestamp': time.time()
                    }),
                    ContentType='application/json'
                )

            except Exception as error_handling_error:
                print(f"  ✗ Failed to handle error: {error_handling_error}")

    print(f"\n✅ Summary: {processed} succeeded, {failed} failed")

    return {
        'statusCode': 200,
        'processed': processed,
        'failed': failed,
        'total': len(pending_requests)
    }
```

**Lambda Configuration:**
```bash
# Create Lambda function
zip -j lambda_process_s3_queue.zip lambda_process_s3_queue.py

aws lambda create-function \
    --function-name Gen3DProcessS3QueueLambda \
    --runtime python3.11 \
    --role arn:aws:iam::ACCOUNT_ID:role/Gen3DLambdaRole \
    --handler lambda_process_s3_queue.lambda_handler \
    --zip-file fileb://lambda_process_s3_queue.zip \
    --timeout 900 \
    --memory-size 1024 \
    --environment "Variables={
        ENDPOINT_NAME=Gen3DSAMEndpoint,
        DATA_BUCKET=gen3d-data-bucket
    }"
```

---

### Step 4: Configure S3 Event Notification

```bash
# Add Lambda permission for S3 to invoke
aws lambda add-permission \
    --function-name Gen3DQueueS3Lambda \
    --statement-id AllowS3InvokeQueue \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::gen3d-data-bucket

# Configure S3 notification
cat > /tmp/s3-notification-queue.json << 'EOF'
{
  "LambdaFunctionConfigurations": [{
    "Id": "Gen3DQueueTrigger",
    "LambdaFunctionArn": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:Gen3DQueueS3Lambda",
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
    --notification-configuration file:///tmp/s3-notification-queue.json
```

---

### Step 5: Optional - Automated Cleanup with S3 Lifecycle

Instead of a Lambda function, use S3 lifecycle policies to automatically clean up old queue files:

```bash
cat > /tmp/s3-lifecycle-queue.json << 'EOF'
{
  "Rules": [
    {
      "Id": "CleanupCompletedRequests",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "users/"
      },
      "Transitions": [],
      "Expiration": {
        "Days": 7
      },
      "NoncurrentVersionExpiration": {
        "NoncurrentDays": 1
      }
    },
    {
      "Id": "CleanupFailedRequests",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "users/"
      },
      "Transitions": [
        {
          "Days": 1,
          "StorageClass": "STANDARD_IA"
        }
      ],
      "Expiration": {
        "Days": 30
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
    --bucket gen3d-data-bucket \
    --lifecycle-configuration file:///tmp/s3-lifecycle-queue.json
```

This automatically:
- Deletes completed requests after 7 days
- Moves failed requests to cheaper storage after 1 day
- Deletes failed requests after 30 days

---

### Step 6: Monitoring Queue Status

**View queue status directly in S3 Console:**
```
S3 Console → gen3d-data-bucket → users → {userId} → queue
  → pending/    (requests waiting for processing)
  → processing/ (currently being processed)
  → completed/  (successfully processed)
  → failed/     (failed requests)
```

**Or via AWS CLI:**
```bash
# Count pending requests
aws s3 ls s3://gen3d-data-bucket/users/ --recursive | grep '/queue/pending/' | wc -l

# Count completed requests
aws s3 ls s3://gen3d-data-bucket/users/ --recursive | grep '/queue/completed/' | wc -l

# Count failed requests
aws s3 ls s3://gen3d-data-bucket/users/ --recursive | grep '/queue/failed/' | wc -l

# View specific request details
aws s3 cp s3://gen3d-data-bucket/users/user123/queue/completed/user123-1234567890-abc.json -
```

---

### Step 7: Testing the Queue

```bash
# Upload test files
aws s3 cp test_image.png s3://gen3d-data-bucket/users/test123/input/12345_image.png
aws s3 cp test_mask.png s3://gen3d-data-bucket/users/test123/input/12345_mask.png

# Check if request was queued
aws s3 ls s3://gen3d-data-bucket/users/test123/queue/pending/

# Wait for endpoint to start (5 minutes)
# ...

# Check if request was processed
aws s3 ls s3://gen3d-data-bucket/users/test123/queue/completed/

# View output
aws s3 ls s3://gen3d-data-bucket/users/test123/output/
```

---

## 💡 Solution 3: Key Advantages

### 1. **Atomic Operations Prevent Race Conditions**

The copy-then-delete pattern ensures only one Lambda processes each request:

```python
# Step 1: Copy to processing/ (multiple Lambdas can do this)
s3_client.copy_object(...)

# Step 2: Delete from pending/ (only ONE will succeed)
s3_client.delete_object(...)  # If this fails, abort processing

# If delete succeeds, you "own" this request
```

### 2. **Visual Queue Inspection**

Unlike DynamoDB, you can **see the queue state visually** in S3 console:
- How many requests are pending?
- Which user has the most requests?
- What's the oldest pending request?
- View full request details with one click

### 3. **Natural Audit Trail**

Completed and failed requests are automatically preserved in S3:
- Full history of all requests
- Easy to query: "How many requests failed last week?"
- No additional cost for audit logs

### 4. **Simplified Debugging**

When something goes wrong:
1. Open S3 console
2. Navigate to `failed/` folder
3. Read the JSON file
4. See exact error message and request details

No need to query DynamoDB or parse CloudWatch logs.

### 5. **Built-in Cleanup**

S3 Lifecycle policies automatically:
- Delete old completed requests
- Archive old failed requests
- No Lambda function needed for cleanup
- Zero operational overhead

---

## 📊 Comparison of Solutions

| Feature | Step Functions | EventBridge + DynamoDB | **EventBridge + S3** |
|---------|---------------|------------------------|----------------------|
| **Complexity** | Medium | Medium | **Low** |
| **Visual Monitoring** | ✅ Yes (console) | ❌ No (logs only) | ✅ **Yes (S3 console)** |
| **Retry Logic** | ✅ Built-in | ❌ Manual | ❌ Manual |
| **State Persistence** | ✅ Automatic | ✅ DynamoDB | ✅ **S3** |
| **Cost** | $0.025/1000 executions | ~$0.01/request | **~$0.0005/request** |
| **Debugging** | ✅ Easy (visual workflow) | ❌ Harder (CloudWatch logs) | ✅ **Easiest (S3 files)** |
| **Lambda Timeout Risk** | ✅ No risk | ✅ No risk | ✅ No risk |
| **Event-Driven** | ⚠️ Polling (every 30s) | ✅ Pure events | ✅ Pure events |
| **Batch Processing** | ❌ One at a time | ✅ Can batch multiple | ✅ Can batch multiple |
| **Audit Trail** | ⚠️ Execution history (90 days) | ❌ Manual | ✅ **Automatic (S3)** |
| **Queue Visibility** | ⚠️ Via API only | ⚠️ Via DynamoDB | ✅ **Visual (S3 console)** |
| **Additional Services** | Step Functions | DynamoDB | **None (S3 only)** |
| **Data Locality** | State separate from data | State in DynamoDB | **State with data (S3)** |
| **Cleanup** | Automatic (90 days) | Manual Lambda | ✅ **S3 Lifecycle** |
| **Best For** | Complex workflows | Structured queries | **Simple, cost-effective** |

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

### EventBridge + S3 Approach (CHEAPEST):
```
100 requests/month:
- EventBridge: Free (included)
- S3 PUT (queue file): 100 × $0.000005 = $0.0005
- S3 COPY (move to processing): 100 × $0.000005 = $0.0005
- S3 LIST (find pending): 1 × $0.005 = $0.005
- S3 GET (read request): 100 × $0.0000004 = $0.00004
- S3 DELETE (cleanup): 200 × $0.0000004 = $0.00008
- S3 storage: 100 items × 1KB × $0.023/GB = $0.0000023
- Total additional cost: ~$0.0006/month (essentially free)
```

**Cost comparison:**
- Solution 1 (Step Functions): $0.003/month
- Solution 2 (DynamoDB): $0.002/month
- **Solution 3 (S3): $0.0006/month** ← **70% cheaper than DynamoDB, 80% cheaper than Step Functions**

**All solutions add < $0.01/month in cost** - essentially free.

---

## 🎯 Recommendation

### Use **EventBridge + S3 (Solution 3)** if: ⭐ **RECOMMENDED**

- ✅ You want the **simplest architecture**
- ✅ You want the **lowest cost** (80% cheaper than Step Functions)
- ✅ You value **visual queue inspection** (S3 console)
- ✅ You want **natural data organization** (state with data)
- ✅ You need **automatic audit trail**
- ✅ You prefer **zero operational overhead** (S3 lifecycle cleanup)
- ✅ You want **easiest debugging** (just read JSON files)
- ✅ You're building a **straightforward queue system**

**Best for**: Most users. Simple, elegant, cost-effective.

---

### Use **Step Functions (Solution 1)** if:

- ✅ You want visual workflow monitoring with execution graphs
- ✅ You prefer AWS-managed state persistence
- ✅ You want built-in retry/error handling
- ✅ You're building complex multi-step workflows
- ✅ You need advanced orchestration (parallel steps, conditions)
- ✅ You value integrated error handling
- ✅ You're comfortable with higher cost ($0.003/month vs $0.0006/month)

**Best for**: Complex workflows with multiple orchestrated steps.

---

### Use **EventBridge + DynamoDB (Solution 2)** if:

- ✅ You need complex queries on queue data (by status, timestamp, user)
- ✅ You want TTL-based automatic cleanup
- ✅ You need transactional updates
- ✅ You're already using DynamoDB extensively
- ✅ You need atomic conditional writes
- ✅ You require sub-millisecond query performance

**Best for**: Applications requiring structured database queries on queue data.

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

### With All Three Solutions:

1. **Request Tracking**: Every request has a unique ID and full history
2. **No Lambda Timeout Risk**: Lambda returns immediately, no waiting for endpoint
3. **Failure Recovery**: Proper error handling and state tracking
4. **Monitoring**: CloudWatch metrics for success/failure rates
5. **Cost Efficiency**: Pay only for execution time, not waiting time
6. **Scalability**: Handles 1 request/month or 10,000/month equally well
7. **User Experience**: Reliable processing with proper error notifications

### Solution 3 (S3) Additional Benefits:

8. **Visual Debugging**: Browse queue folders in S3 console
9. **Natural Organization**: Queue state lives with data
10. **Zero Cleanup Cost**: S3 lifecycle policies handle it
11. **Built-in Audit Trail**: Completed/failed requests preserved
12. **Simplest Architecture**: No additional services beyond S3

---

## 🔧 Next Steps

**Primary Recommendation**: Implement **Solution 3 (EventBridge + S3)** for:
- Simplest architecture
- Lowest cost (80% cheaper)
- Easiest debugging
- Best for most use cases

**Alternative**: Implement **Solution 1 (Step Functions)** if you need complex workflow orchestration.

**Deployment Options:**
1. Update the Cost Analysis document to replace Option 3 with EventBridge + S3 approach
2. Update the Implementation Plan v1.1 with chosen solution deployment steps
3. Create automated deployment scripts for your chosen solution
4. Set up monitoring and alerting for the queue system

---

## 📝 Decision Matrix

| Requirement | Solution 1 | Solution 2 | Solution 3 |
|-------------|-----------|-----------|-----------|
| Simple architecture | ⚠️ Medium | ⚠️ Medium | ✅ **Best** |
| Lowest cost | ❌ $0.003 | ⚠️ $0.002 | ✅ **$0.0006** |
| Visual monitoring | ✅ Workflow | ❌ None | ✅ **S3 console** |
| Easy debugging | ✅ Good | ❌ Logs only | ✅ **Easiest** |
| Complex workflows | ✅ **Best** | ❌ No | ❌ No |
| Built-in retries | ✅ **Yes** | ❌ Manual | ❌ Manual |
| Audit trail | ⚠️ 90 days | ❌ Manual | ✅ **Automatic** |
| Learning curve | ⚠️ Medium | ⚠️ Medium | ✅ **Low** |
| Operational overhead | ✅ Low | ⚠️ Medium | ✅ **Lowest** |

**Winner for Gen3D**: **Solution 3 (EventBridge + S3)** ⭐

---

**Document Version**: 2.0
**Date**: 2025-11-27
**Last Updated**: Added Solution 3 (EventBridge + S3)
**Status**: Ready for Implementation ✅
