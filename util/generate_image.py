#!/usr/bin/env python3
""" Script to generate images after stacks have been deployed successfully.
"""
import argparse
import pathlib
from typing import cast, Any, Dict, TypedDict

import boto3
import tomli


class Parameters(TypedDict):
    """
    Data structure of get_parameters() result.
    """

    bucketName: str
    endpointName: str


def get_config() -> Dict[str, Any]:
    """
    Get config from config.toml

    Returns:
    --------
    dict
        The config.toml data.
    """
    with open(
        file=pathlib.Path(__file__).parent.parent / "config" / "config.toml",
        mode="rb",
    ) as config_file:
        return tomli.load(config_file)


def get_parameters(
    region: str,
    repository_name: str,
) -> Parameters:
    """
    Get parameters from SSM

    Parameters:
    -----------
    region : str
        The region from config.toml, e.g. "eu-central-1"
    repository_name : str
        The repository_name from config.toml

    Returns:
    --------
    Parameters
        The parameters required to start an inference.
    """
    ssm_client = boto3.client(service_name="ssm", region_name=region)
    get_parameters_response = ssm_client.get_parameters_by_path(
        Path=f"/simple-gen-ai-service/{repository_name}/"
    )
    return cast(
        Parameters,
        {
            parameter["Name"].split("/")[-1]: parameter["Value"]
            for parameter in get_parameters_response["Parameters"]
        },
    )


def start_async_image_generation(
    bucket_name: str,
    endpoint_name: str,
    request_input_file_path: str,
    region_name: str,
) -> str:
    """
    Start image generation

    Parameters:
    -----------
    bucket_name : str
        The name of the S3 bucket as stored in the parameters
    endpoint_name : str
        The name of the SageMaker endpoint as stored in the parameters
    request_input_file_path : str
        The full path to the inference request input file
    region_name : str
        The region from config.toml, e.g. "eu-central-1"

    Returns:
    --------
    inference_id : str
        The id of the started inference
    """
    sagemaker_runtime_client = boto3.client(
        service_name="sagemaker-runtime", region_name=region_name
    )
    s3_client = boto3.client(service_name="s3", region_name=region_name)
    request_input_file = pathlib.Path(request_input_file_path)
    file_key = "requests/" + request_input_file.name
    s3_client.upload_file(
        Filename=request_input_file_path,
        Bucket=bucket_name,
        Key=file_key,
    )
    invoke_response = sagemaker_runtime_client.invoke_endpoint_async(
        EndpointName=endpoint_name,
        InputLocation=f"s3://{bucket_name}/{file_key}",
        InvocationTimeoutSeconds=3600,
        ContentType="application/json",
    )
    return invoke_response["InferenceId"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--request-input-file",
        help="full path to inference request input file",
        required=True,
    )
    args = parser.parse_args()

    config = get_config()
    parameters = get_parameters(
        region=config["CONFIG"]["region"],
        repository_name=config["CONFIG"]["repository_name"],
    )
    inference_id = start_async_image_generation(
        bucket_name=parameters["bucketName"],
        endpoint_name=parameters["endpointName"],
        region_name=config["CONFIG"]["region"],
        request_input_file_path=args.request_input_file,
    )

    print(
        f"Inference was started with id: {inference_id}.\n"
        f"Expect a result in s3://{parameters['bucketName']}/images/{inference_id}\n\n"
        "Check for available results with:\n"
        f"aws s3 ls s3://{parameters['bucketName']}/images/{inference_id}/\n\n"
        "You can describe the endpoint with:\n"
        f"aws sagemaker describe-endpoint --endpoint-name {parameters['endpointName']}\n\n"
    )
