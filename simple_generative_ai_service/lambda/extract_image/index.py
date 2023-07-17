#!/usr/bin/env python3

"""
Extract image from SageMaker asynchronous image outputs. Triggered by SNS success topic messages.
"""

import io
import json
import os
from typing import Any, IO, List, TypedDict, Union

import aws_lambda_powertools
import boto3
import botocore.exceptions
import botocore.response
import mypy_boto3_s3.type_defs as s3_type_defs
from PIL import Image


BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
if not BUCKET_NAME:
    raise EnvironmentError("BUCKET_NAME environment variable is required")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
S3_KEY_PREFIX = "images/"

with open(
    file="test_image_data.json", mode="r", encoding="utf8"
) as test_image_data_file:
    TEST_IMAGE_DATA: List[List[List[int]]] = json.load(test_image_data_file)


logger = aws_lambda_powertools.Logger()
s3 = boto3.client("s3")


def load_data_from_s3(s3_uri: str):
    """
    Load JSON data from the given S3 URI and return it as a dict.

    Parameters:
    -----------
    s3_uri : str
        The S3 URI of the JSON data to load.

    Returns:
    --------
    dict
        The JSON data loaded from the S3 URI.

    Notes:
    ------
    The S3 URI is expected to be in the format: s3://<bucket>/<key>.
    """
    _, _, bucket, key = s3_uri.split("/", 3)

    response: Union[s3_type_defs.GetObjectOutputTypeDef, None] = None
    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=key,
        )
    except botocore.exceptions.ClientError as error:
        logger.info(
            "Got client error when trying to load data from %s: %s", s3_uri, error
        )
        return None

    body = response.get("Body", None)
    if not body:
        logger.info("Could not load data from S3 URI: %s", s3_uri)
        return None

    data_json = body.read()
    return json.loads(data_json)


def decode_image_to_png(data: List[List[List[int]]]) -> bytes:
    """
    Decode an image given as a nested list of rows, columns, and RGB tuples into PNG.

    Parameters:
    -----------
    data : List[List[List[int]]]
        A nested list of rows, columns, and RGB tuples.

    Returns:
    --------
    bytes
        The PNG image data.

    Notes:
    ------
    The nested list of rows, columns, and RGB tuples is expected to be in the format:
    [
        [
            [r, g, b], [r, g, b], [r, g, b], [r, g, b],
        ],
    ]
    """
    image = Image.new("RGB", (len(data[0]), len(data)))
    for y_coord, row in enumerate(data):
        for x_coord, color in enumerate(row):
            image.putpixel((x_coord, y_coord), tuple(color))

    result = None
    with io.BytesIO() as png_buffer:
        image.save(png_buffer, "PNG")
        result = png_buffer.getvalue()

    return result


def test_decode_image_to_png() -> None:
    """
    Tests that the decode_image_to_png function works as expected.

    The test image is expected to be the same as the TEST_IMAGE_DATA constant.

    Raises:
    -------
        ValueError: If the test image does not match the expected TEST_IMAGE_DATA.
    """
    result = decode_image_to_png(TEST_IMAGE_DATA)
    with io.BytesIO(result) as png_buffer:
        with Image.open(png_buffer) as image:
            for y_coord, row in enumerate(TEST_IMAGE_DATA):
                for x_coord, pixel in enumerate(row):
                    image_pixel = list(image.getpixel((x_coord, y_coord))[:3])
                    if not pixel == image_pixel:
                        raise ValueError(
                            f"pixel value '{str(pixel)}' not as expected ('{str(image_pixel)}')",
                        )


def decode_image_data(data) -> Union[List[bytes], None]:
    """
    Decode a set of images from the given JSON data. Images are returned as a list of PNG images
    (Bytes).

    Example output JSON from S3 output directory containing the image:
    -------

    {
        "generated_images": [
            [
                [
                    [208, 165, 83], [226, 176, 72], [229, 188, 73], [234, 197, 77],
                    ...
                ]
            ]
        ],
        "prompt": "astronaut on a horse"
    }"""
    images_raw = data.get("generated_images", None)
    if not images_raw or not isinstance(images_raw, list):
        logger.info("Invalid image data. Unable to decode.")
        return None

    result: List[bytes] = []
    for i in images_raw:
        result.append(decode_image_to_png(i))

    return result


def save_image_to_s3(
    image: Union[str, bytes, IO, botocore.response.StreamingBody], key: str
) -> bool:
    """
    Save the given image to S3 under the given key.

    Parameters:
    -----------
    image : Union[str, bytes, IO, botocore.response.StreamingBody]
        The image to save.
    key : str
        The S3 key to save the image under.

    Returns:
    --------
    bool
        True if the image was saved successfully, False otherwise.
    """
    try:
        s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=image, ContentType="image/png")
    except botocore.exceptions.ClientError as error:
        logger.info("Got client error when trying to save image to %s: %s", key, error)
        return False

    return True


class EventData(TypedDict):
    """
    Data structure for the result of the get_event_data function.
    """

    inference_id: str
    output_data: Any


def get_event_data(event: dict) -> Union[EventData, None]:
    """
    Get relevant data for further processing from the event received by the AWS Lambda function.

    Parameters:
    -----------
    event : dict
        The event received by the AWS Lambda function.

    Returns:
    --------
    EventData
        The relevant data for further processing.
    """

    # extract_image has some same code as save_message - not enough to warrant introducting a
    # Lambda Layer though.
    # pylint: disable=duplicate-code
    # Perform basic checks on the given event.
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

    message_json = event["Records"][0]["Sns"]["Message"]
    message = json.loads(message_json)

    # If we find an inference ID, then this message is related to a particular inference job.
    inference_id = message.get("inferenceId", None)
    if (
        not inference_id
    ):  # If we find no inference ID, the it's probably a test message. Ignore.
        logger.info("No inferenceId found in message: %s. Ignoring.", message_json)
        return None

    invocation_status = message.get("invocationStatus", None)
    if invocation_status.lower() != "completed":
        logger.info(
            "Invocation status is not completed: %s. Ignoring.", invocation_status
        )
        return None

    response_parameters = message.get("responseParameters", None)
    if not response_parameters or not isinstance(response_parameters, dict):
        logger.info(
            "Invalid response parameters found in message: %s. Ignoring.", message_json
        )
        return None

    output_location = response_parameters.get("outputLocation", None)
    if not output_location or not output_location.startswith("s3://"):
        logger.info("Invalid output location: %s. Ignoring.", output_location)
        return None

    logger.info("Loading raw image data from: %s", output_location)
    output_data = load_data_from_s3(output_location)
    if not output_data:
        logger.info("Unable to load output data.")
        return None

    return {
        "inference_id": inference_id,
        "output_data": output_data,
    }


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, _):
    """Lambda function for processing SageMaker asynchronous SNS success messages.

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
    Nothing. Saves the success message to Amazon S3 and processes the output given in the message.

    Example event
    -------------
    # pylint: disable=line-too-long
    {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventVersion": "1.0",
                "EventSubscriptionArn": "arn:aws:sns:eu-central-1:xxxxxxxxxxxx:test-Endpoint-SuccessTopic495EEDDD-GJWMb3rWWDVU:a67de9ed-3acd-4fd5-862f-309c4232f93d",
                "Sns": {
                    "Type": "Notification",
                    "MessageId": "e81b8b22-05f2-5a14-b9d5-d772adef4afa",
                    "TopicArn": "arn:aws:sns:eu-central-1:xxxxxxxxxxxx:test-Endpoint-SuccessTopic495EEDDD-GJWMb3rWWDVU",
                    "Subject": null,
                    "Message": "{\"awsRegion\":\"eu-central-1\",\"eventTime\":\"2023-01-29T16:59:09.174Z\",\"receivedTime\":\"2023-01-29T16:49:47.144Z\",\"invocationStatus\":\"Completed\",\"requestParameters\":{\"endpointName\":\"ep-m-js-sd-2023-01-24-0-4\",\"inputLocation\":\"s3://test-endpoint-sdmodeliobucket1e5ea53d-1tobu502c03zo/input/test_request.json\"},\"responseParameters\":{\"contentType\":\"application/json\",\"outputLocation\":\"s3://test-endpoint-sdmodeliobucket1e5ea53d-1tobu502c03zo/output/37a32ca5-ded4-4fd4-ac70-0afc8a901080.out\"},\"inferenceId\":\"4bad2b42-25c8-43af-9ed7-26c24d4ee74e\",\"eventVersion\":\"1.0\",\"eventSource\":\"aws:sagemaker\",\"eventName\":\"InferenceResult\"}",
                    "Timestamp": "2023-01-29T16:59:09.210Z",
                    "SignatureVersion": "1",
                    "Signature": "wRoXg9By3GFCiF29DaLI4Tod6lGycyaOA+h4GRW1/dMEgKww2R9xjx9scYTzUdcdtj729krLJTWJmXE1xMB+9ipoGNb/lbno/epwOwZF08CaI1fJb+c0hxyBqYAFFLgYqIk3nrIYkem0nwq3n1MzSq3XnzhFcppNL+FO72N87/n8VcUw3BNzCWXYBK2Ry8+CMa3vTVcYXOmEDn114+GD54uabBRuH8MzMZV296I2aUcNAuKTmEG8hgR7nfPIl1FGGPWD8wIAKgH8uVysM/dcf/CnG1H4nIrJlx7VKCe0f/JnwPApjUzH5Q/Hi1Uet9nhCqmzxbRMYNs3y5OX2hef1w==",
                    "SigningCertUrl": "https://sns.eu-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
                    "UnsubscribeUrl": "https://sns.eu-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:eu-central-1:xxxxxxxxxxxx:test-Endpoint-SuccessTopic495EEDDD-GJWMb3rWWDVU:a67de9ed-3acd-4fd5-862f-309c4232f93d",
                    "MessageAttributes": {}
                }
            }
        ]
    }
    """

    event_data = get_event_data(event=event)
    if not event_data:
        return

    # We now have all images. Decode and save them.
    images = decode_image_data(event_data["output_data"])
    prompt = event_data["output_data"].get("prompt", "image")
    image_name_base = "_".join(
        prompt.split(" ")[:5]
    )  # Limit prompt to 5 words and concatenate them with '_'.
    image_key_prefix = f"{S3_KEY_PREFIX}{event_data['inference_id']}/{image_name_base}"
    saved_image_keys = []

    for num, img in enumerate(images):
        key = f"{image_key_prefix}_{num}.png"
        logger.info("Saving image %s as: %s", num, key)
        if save_image_to_s3(img, key):
            saved_image_keys.append(key)

    if len(saved_image_keys) == len(images):
        logger.info("%d/%d saved successfully.", len(saved_image_keys), len(images))
    else:
        logger.warning(
            "Unable to save all images, only %d/%d succeeded.",
            len(saved_image_keys),
            len(images),
        )

    # Finally, save a manifest of all images to allow for image number verification.
    image_manifest_key = f"{S3_KEY_PREFIX}{event_data['inference_id']}/manifest.json"
    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=image_manifest_key,
            Body=json.dumps(
                {
                    "imageId": event_data["inference_id"],
                    "prompt": prompt,
                    "imageKeys": saved_image_keys,
                },
                sort_keys=True,
                indent=4,
            ),
            ContentType="application/json",
        )
    except botocore.exceptions.ClientError as error:
        logger.info(
            "Got client error when trying to save image generation manifest to %s: %s",
            image_manifest_key,
            error,
        )
