"""
This CDK stack defines an Amazon SageMaker endpoint for hosting a Text to Image model on AWS.
It is part of an upstream deployment stage.
"""

import aws_cdk as cdk
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_lambda_event_sources as lambda_event_sources
import aws_cdk.aws_lambda_python_alpha as lambda_python_alpha
import aws_cdk.aws_logs as logs
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_sns as sns
import constructs

from simple_generative_ai_service.jumpstart_async_endpoint_construct import (
    JumpStartAsyncEndpoint,
)
from .config import config


class ServiceEndpointStack(cdk.Stack):
    """
    CDK stack describing the Service Endpoint
    """

    def create_save_message_function(  # pylint: disable=too-many-arguments
        self,
        powertools_layer: lambda_.ILayerVersion,
        bucket: s3.Bucket,
        error_topic: sns.Topic,
        success_topic: sns.Topic,
        powertools_service_name: str,
        powertools_metrics_namespace: str,
    ) -> lambda_python_alpha.PythonFunction:
        """
        Create the save_message Lambda function.

        Parameters:
        -----------
        powertools_layer: lambda_.ILayerVersion
            The powertools layer.
        bucket: s3.Bucket
            The S3 bucket to save messages to.
        error_topic: sns.Topic
            The SNS topic to publish error messages to.
        success_topic: sns.Topic
            The SNS topic to publish success messages to.
        powertools_service_name: str
            The name of the powertools service.
        powertools_metrics_namespace: str
            The namespace of the powertools metrics.

        Returns:
        --------
        lambda_python_alpha.PythonFunction
            The save_message Lambda function.
        """
        save_message_function = lambda_python_alpha.PythonFunction(
            self,
            "SaveMessageFunction",
            entry="simple_generative_ai_service/lambda/save_message",
            index="index.py",
            handler="lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            layers=[powertools_layer],
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": powertools_service_name,
                "POWERTOOLS_METRICS_NAMESPACE": powertools_metrics_namespace,
            },
            log_retention=logs.RetentionDays.TWO_WEEKS,
        )

        bucket.grant_write(save_message_function)

        save_message_function.add_event_source(
            lambda_event_sources.SnsEventSource(error_topic)
        )
        save_message_function.add_event_source(
            lambda_event_sources.SnsEventSource(success_topic)
        )

        return save_message_function

    def create_extract_image_function(  # pylint: disable=too-many-arguments
        self,
        bucket: s3.Bucket,
        success_topic: sns.Topic,
        powertools_layer: lambda_.ILayerVersion,
        powertools_service_name: str,
        powertools_metrics_namespace: str,
    ) -> lambda_python_alpha.PythonFunction:
        """
        Create the extract_image Lambda function.

        Parameters:
        -----------
        bucket: s3.Bucket
            The S3 bucket read input from and save images to.
        success_topic: sns.Topic
            The SNS topic acting as event source.
        powertools_layer: lambda_.ILayerVersion
            The powertools layer.
        powertools_service_name: str
            The name of the powertools service.
        powertools_metrics_namespace: str
            The namespace of the powertools metrics.

        Returns:
        --------
        lambda_python_alpha.PythonFunction
            The extract_image Lambda function.
        """
        extract_image_function = lambda_python_alpha.PythonFunction(
            self,
            "ExtractImageFunction",
            entry="simple_generative_ai_service/lambda/extract_image",
            index="index.py",
            handler="lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            memory_size=1024,
            timeout=cdk.Duration.seconds(60),
            layers=[powertools_layer],
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "LOG_LEVEL": "INFO",
                "POWERTOOLS_SERVICE_NAME": powertools_service_name,
                "POWERTOOLS_METRICS_NAMESPACE": powertools_metrics_namespace,
            },
            log_retention=logs.RetentionDays.TWO_WEEKS,
        )

        bucket.grant_read_write(extract_image_function)

        extract_image_function.add_event_source(
            lambda_event_sources.SnsEventSource(success_topic)
        )

        return extract_image_function

    def __init__(
        self, scope: constructs.Construct, construct_id: str, **kwargs
    ) -> None:
        super().__init__(scope=scope, id=construct_id, **kwargs)

        self.endpoint = JumpStartAsyncEndpoint(
            scope=self,
            construct_id="ServiceEndpoint",
            jumpstart_model_id=config["CONFIG"]["jumpstart_model_id"],
            jumpstart_model_version=config["CONFIG"]["jumpstart_model_version"],
            jumpstart_model_region=config["CONFIG"]["region"],
            jumpstart_model_environment=config["CONFIG"]["jumpstart_model_environment"],
            instance_type=config["CONFIG"]["instance_type"],
            max_capacity=config["CONFIG"]["max_capacity"],
        )

        powertools_layer = lambda_python_alpha.PythonLayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPython:19",
        )

        self.create_save_message_function(
            powertools_layer=powertools_layer,
            bucket=self.endpoint.bucket,
            error_topic=self.endpoint.error_topic,
            success_topic=self.endpoint.success_topic,
            powertools_service_name=config["CONFIG"]["powertools_service_name"],
            powertools_metrics_namespace=config["CONFIG"][
                "powertools_metrics_namespace"
            ],
        )

        self.create_extract_image_function(
            bucket=self.endpoint.bucket,
            success_topic=self.endpoint.success_topic,
            powertools_layer=powertools_layer,
            powertools_service_name=config["CONFIG"]["powertools_service_name"],
            powertools_metrics_namespace=config["CONFIG"][
                "powertools_metrics_namespace"
            ],
        )
