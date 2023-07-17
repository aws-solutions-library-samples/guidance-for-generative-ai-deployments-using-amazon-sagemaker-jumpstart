#!/usr/bin/env python3

"""
Save error and success messages from Amazon SageMaker asynchronous inference executions.
Triggered by SNS Topic messages.
"""

import json
import os

import aws_lambda_powertools
import boto3

BUCKET_NAME = os.environ.get("BUCKET_NAME", None)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


logger = aws_lambda_powertools.Logger()
s3 = boto3.resource("s3")


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, _):
    """Lambda function for processing SageMaker async inference success notifications.

    Parameters
    ----------
    event: dict, expecting to be called from an SNS trigger.
        Lambda Event Input Format

        Event doc: https://docs.aws.amazon.com/lambda/latest/dg/lambda-invocation.html

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    -------
    Nothing. Save the message content into an s3 bucket.

    Example event
    -------------
    # pylint: disable=line-too-long
    {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventVersion": "1.0",
                "EventSubscriptionArn": "arn:aws:sns:eu-central-1:xxxxxxxxxxxx:test-Endpoint-ErrorTopicA0904A23-M7BXXkERB48E:5cbccb78-232c-4f73-bd29-48d218f9a8c6",
                "Sns": {
                    "Type": "Notification",
                    "MessageId": "4a544bca-57f1-59ba-a7d2-179acf8df090",
                    "TopicArn": "arn:aws:sns:eu-central-1:xxxxxxxxxxxx:test-Endpoint-ErrorTopicA0904A23-M7BXXkERB48E",
                    "Subject": null,
                    "Message": "{\"awsRegion\":\"eu-central-1\",\"eventTime\":\"2023-01-29T15:52:28.711Z\",\"receivedTime\":\"2023-01-29T12:11:05.618Z\",\"invocationStatus\":\"Failed\",\"failureReason\":\"ClientError: Received client error (400) from model. See the SageMaker Endpoint logs in your account for more information.\",\"requestParameters\":{\"endpointName\":\"ep-m-js-sd-2023-01-24-0-4\",\"inputLocation\":\"s3://test-endpoint-sdmodeliobucket1e5ea53d-1tobu502c03zo/input/test_request_broken.json\"},\"inferenceId\":\"43591795-1ef7-417a-9402-ae901b57dc55\",\"eventVersion\":\"1.0\",\"eventSource\":\"aws:sagemaker\",\"eventName\":\"InferenceResult\"}",
                    "Timestamp": "2023-01-29T15:52:28.716Z",
                    "SignatureVersion": "1",
                    "Signature": "Ny9iFMAfimFS6yA+IV7YOTX5zhOT6hKfl0gE6khhA34gHQrwylNlHQSu9DC1w+nxmkdJBDzHoqnBceBPGmEQDvPCNLmvm+d/3u2Vk+MFxiJX8NTzb0htfoNEoiIxwL9Nbw1/ujkJuqM0qwLakgtMPEDE6RkCvEsXiLyKZsbcv9ggSghYZwST/bmcMWYt7D8ej5/SL8xYEnesHvugaWnpkA43vvxfUphAhwB2ocDLqQHFRDfufVNU9dEHCzEujUJAhr7WbGZ1O0pE7qinKSgGYwvVOMdgXSj3um/btclMs2z8aMTmUSmJ4OjmmiwUPcyoVIjxsTmPTPKWLivBZgeQGg==",
                    "SigningCertUrl": "https://sns.eu-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
                    "UnsubscribeUrl": "https://sns.eu-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:eu-central-1:xxxxxxxxxxxx:test-Endpoint-ErrorTopicA0904A23-M7BXXkERB48E:5cbccb78-232c-4f73-bd29-48d218f9a8c6",
                    "MessageAttributes": {}
                }
            }
        ]
    }

    """
    if "Records" not in event and len(event["Records"]) == 1:
        raise ValueError(
            "Invalid event. Expected 'Records' in event with exactly one entry. "
            + f"Instead got:\n{event}"
        )
    if "Sns" not in event["Records"][0]:
        raise ValueError(
            "Invalid event. Expected 'Sns' in event['Records'][0]. "
            + f"Instead got:\n{event}"
        )
    if "Message" not in event["Records"][0]["Sns"]:
        raise ValueError(
            "Invalid event. Expected 'Message' in event['Records'][0]['Sns']. "
            + f"Instead got:\n{event}"
        )

    # Extract the Amazon SageMaker error message from the SNS message.
    message_json = event["Records"][0]["Sns"]["Message"]
    message = json.loads(message_json)

    # If we find an inference ID, then this message is related to a particular inference job.
    inference_id = message.get("inferenceId", None)
    if inference_id:
        key = "messages/" + inference_id + ".json"

        logger.info("Writing message to s3://%s/%s", BUCKET_NAME, key)
        s3.Object(BUCKET_NAME, key).put(Body=message_json)
    else:  # May be a test message. Ignore it.
        logger.info("No inferenceId found in message: %s. Ignoring.", message_json)
