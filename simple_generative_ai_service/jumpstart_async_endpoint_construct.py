"""
An AWS CDK Level 2 Construct for an Amazon SageMaker endpoint, hosting a given
Amazon SageMaker JumpStart model in asynchronous mode.
"""

from typing import Union

import aws_cdk
import aws_cdk.aws_applicationautoscaling as applicationautoscaling
import aws_cdk.aws_cloudwatch as cloudwatch
import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_sagemaker as cdk_sagemaker
import aws_cdk.aws_sns as sns
import aws_cdk.aws_ssm as ssm
import constructs

from simple_generative_ai_service.jumpstart_model_construct import JumpStartModel
from .config import config


MAX_ENDPOINT_CONFIG_NAME_SIZE = 63


def create_async_inference_config(
    bucket_name: str,
    error_topic: Union[sns.Topic, None] = None,
    success_topic: Union[sns.Topic, None] = None,
    max_concurrent_invocations_per_instance: int = 1,
) -> cdk_sagemaker.CfnEndpointConfig.AsyncInferenceConfigProperty:
    """
    Create a standard SageMaker Asynchronous Inference configuration for the
    given S3 bucket name.

    Parameters:
    -----------
    bucket_name : str
        The name of an Amazon S3 bucket to use for creating this configuration.
    error_topic : Topic | None
        The Amazon SNS Topic to use for posting error messages.
    success_topic : Topic | None
        The Amazon SNS Topic to use for posting success messages.
    max_concurrent_invocations_per_instance : int
        The maximum number of concurrent invocations to support in this config.

    Returns:
    --------
    CfnEndpointConfig.AsyncInferenceConfigProperty
        An Amazon SageMaker asynchronous inference endpoint configuration property.
    """

    return cdk_sagemaker.CfnEndpointConfig.AsyncInferenceConfigProperty(
        client_config=cdk_sagemaker.CfnEndpointConfig.AsyncInferenceClientConfigProperty(
            max_concurrent_invocations_per_instance=max_concurrent_invocations_per_instance
        ),
        output_config=cdk_sagemaker.CfnEndpointConfig.AsyncInferenceOutputConfigProperty(
            s3_output_path=f"s3://{bucket_name}/output/",
            notification_config=(
                cdk_sagemaker.CfnEndpointConfig.AsyncInferenceNotificationConfigProperty(
                    error_topic=error_topic.topic_arn if error_topic else None,
                    success_topic=success_topic.topic_arn if success_topic else None,
                )
            ),
        ),
    )


def create_production_variant(
    model_name: str, instance_type: str
) -> cdk_sagemaker.CfnEndpointConfig.ProductionVariantProperty:
    """
    Create a standard production variant for the given model name.

    Parameters:
    -----------
    model_name : str
        The name of the model to use for this variant.
    instance_type : str
        The Amazon EC2 instance type to use.

    Returns:
    --------
    CfnEndpointConfig.ProductionVariantProperty
        A production variant property.
    """
    return cdk_sagemaker.CfnEndpointConfig.ProductionVariantProperty(
        initial_variant_weight=1.0,
        model_name=model_name,
        variant_name=model_name,
        accelerator_type=None,
        container_startup_health_check_timeout_in_seconds=None,
        initial_instance_count=1,
        instance_type=instance_type,
        model_data_download_timeout_in_seconds=None,
        serverless_config=None,
        volume_size_in_gb=None,
    )


class JumpStartAsyncEndpoint(constructs.Construct):
    """
    This AWS CDK V2 Construct hosts the given Amazon SageMaker JumpStart model
    in an Amazon SageMaker Endpoint, using asynchronous mode. It provides
    sensible defaults to minimize input, and some customization possibilities.
    It also creates and exposes all necessary or useful additional constructs,
    such as the Model, an S3 bucket for IO, and SNS topics.
    """

    def create_model_execution_role(self, bucket: s3.Bucket) -> iam.Role:
        """
        Create a role for SageMaker to use when executing the model.
        The code that creates the model will add model-specific permissions.

        Parameters:
        -----------
        bucket : Bucket
            An Amazon S3 Bucket resource.

        Returns:
        --------
        Role
            An Amazon IAM Role resource.
        """
        role = iam.Role(
            scope=self,
            id="ModelExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
        )

        bucket.grant_read_write(role)

        return role

    def create_jumpstart_model(  # pylint: disable=too-many-arguments
        self,
        construct_id: str,
        role: iam.Role,
        inference_instance_type: str,
        jumpstart_model_id: str,
        jumpstart_model_region: str,
        jumpstart_model_version: str,
        jumpstart_model_environment: Union[dict, None] = None,
    ) -> JumpStartModel:
        """
        Create the SageMaker Model based on the given parameters.
        Use the specialized JumpStartModel class.

        Parameters:
        -----------
        jumpstart_model_id : str
            The AWS SageMaker JumpStart ID for this model.
        jumpstart_model_version : str
            The version of the JumpStart model.
        jumpstart_model_region : str
            The AWS region to use for this model.
        jumpstart_model_environment : dict
            A dictionary of environment variables to use for the model.
        inference_instance_type : str
            The SageMaker instance type to use for this model. This is needed
            to infer a compatible container image.
        role : Role
            An Amazon IAM Role resource.

        Returns:
        --------
        JumpStartModel
            A AWS CDK V2 SageMaker JumpStart Model resource.

        """
        container_environment = {
            "SAGEMAKER_CONTAINER_LOG_LEVEL": 20,
            "SAGEMAKER_PROGRAM": "inference.py",
            "SAGEMAKER_REGION": jumpstart_model_region,
        }
        if jumpstart_model_environment:
            container_environment.update(jumpstart_model_environment)

        return JumpStartModel(
            self,
            construct_id,
            jumpstart_model_id=jumpstart_model_id,
            jumpstart_model_version=jumpstart_model_version,
            jumpstart_model_region=jumpstart_model_region,
            inference_instance_type=inference_instance_type,
            container_environment=container_environment,
            role=role,
        )

    def create_endpoint_configuration(
        self,
        construct_id: str,
        model: cdk_sagemaker.CfnModel,
        production_variant: cdk_sagemaker.CfnEndpointConfig.ProductionVariantProperty,
        async_inference_config: cdk_sagemaker.CfnEndpointConfig.AsyncInferenceConfigProperty,
    ) -> cdk_sagemaker.CfnEndpointConfig:
        """
        Build a SageMaker asynchronous endpoint configuration based on the given
        parameters.

        Parameters:
        -----------
        construct_id : str
            The AWS CDK scoped id of this resource.
        model : CfnModel
            The model to use for the endpoint.
        production_variant : CfnEndpointConfig.ProductionVariantProperty
            A production variant configuration for the endpoint.
        async_inference_config : CfnEndpointConfig.AsyncInferenceConfigProperty
            The asynchronous inference configuration to use.

        Returns:
        --------
        CfnEndpointConfig
            A AWS CDK V2 SageMaker endpoint configuration
        """
        if not model.model_name:
            raise ValueError("Model name is not defined.")

        endpoint_config_name = (
            "epc-" + model.model_name[-(MAX_ENDPOINT_CONFIG_NAME_SIZE - 4) :]
        )
        endpoint_configuration = cdk_sagemaker.CfnEndpointConfig(
            scope=self,
            id=construct_id,
            production_variants=[production_variant],
            async_inference_config=async_inference_config,
            data_capture_config=None,
            endpoint_config_name=endpoint_config_name,
            explainer_config=None,
            kms_key_id=None,
            shadow_production_variants=None,
            tags=None,
        )
        # Add a dependency from the model to the endpoint configuration to allow
        # CloudFormation to check the model before setting up the endpoint.
        endpoint_configuration.node.add_dependency(model)

        return endpoint_configuration

    def create_scaling_policy(
        self,
        construct_id: str,
        endpoint: Union[cdk_sagemaker.CfnEndpoint, None] = None,
        production_variant: Union[
            cdk_sagemaker.CfnEndpointConfig.ProductionVariantProperty, None
        ] = None,
        max_capacity: int = 1,
    ) -> applicationautoscaling.StepScalingPolicy:
        """
        Configure AWS Application Autoscaling for the given SageMaker endpoint.
        See:
        https://docs.aws.amazon.com/sagemaker/latest/dg/
            async-inference-autoscale.html
        https://docs.aws.amazon.com/cdk/api/v2/python/
            aws_cdk.aws_applicationautoscaling/README.html

        Parameters:
        -----------
        construct_id : str
            The AWS CDK scoped id of this resource.
        endpoint : CfnEndpoint
            The AWS CDK V2 SageMaker endpoint resource.
        production_variant : CfnEndpointConfig.ProductionVariantProperty
            A production variant configuration property for the endpoint.

        Returns:
        --------
        StepScalingPolicy
            An AWS CDK V2 StepScalingPolicy resource.

        """
        if endpoint is None:
            raise ValueError("Endpoint attribute cannot be None.")
        if production_variant is None:
            raise ValueError("Production variant attribute cannot be None.")

        resource_id = (
            f"endpoint/{endpoint.endpoint_name}/"
            + f"variant/{production_variant.variant_name}"
        )
        scalable_target = applicationautoscaling.ScalableTarget(
            scope=self,
            id=construct_id,
            max_capacity=max_capacity,
            min_capacity=0,
            resource_id=resource_id,
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            service_namespace=applicationautoscaling.ServiceNamespace.SAGEMAKER,
        )
        scalable_target.node.add_dependency(endpoint)

        if not endpoint.endpoint_name:
            raise ValueError("endpoint_name not set for endpoint")

        # ApproximateBacklogSizePerInstance may return "Insufficient data".
        # Therefore, we use Step Scaling which can deal with this.
        # See also: https://stackoverflow.com/questions/65322286/
        #     aws-sagemaker-inference-endpoint-doesnt-scale-in-with-autoscaling
        approximate_backlog_metric = cloudwatch.Metric(
            metric_name="ApproximateBacklogSizePerInstance",
            namespace="AWS/SageMaker",
            dimensions_map={"EndpointName": endpoint.endpoint_name},
            statistic="Average",
            period=aws_cdk.Duration.minutes(5),
        )

        scaling_policy = applicationautoscaling.StepScalingPolicy(
            scope=self,
            id="ScalingPolicy",
            scaling_target=scalable_target,
            metric=approximate_backlog_metric,
            scaling_steps=[
                applicationautoscaling.ScalingInterval(change=-1, upper=0.5, lower=0.0),
                applicationautoscaling.ScalingInterval(change=1, upper=None, lower=0.5),
            ],
            adjustment_type=applicationautoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=aws_cdk.Duration.minutes(
                config["CONFIG"]["endpoint_cooldown_minutes"]
            ),
            datapoints_to_alarm=1,
            evaluation_periods=1,
            metric_aggregation_type=None,
            min_adjustment_magnitude=None,
        )

        return scaling_policy

    def __init__(
        self,
        scope: constructs.Construct,
        construct_id: str,
        instance_type: str,
        *,
        jumpstart_model_id: str,
        jumpstart_model_region: str,
        max_capacity: int,
        jumpstart_model_version: str = "*",
        jumpstart_model_environment: Union[dict, None] = None,
    ) -> None:
        """
        Initialize this JumpStartAsyncEndpoint class.

        Parameters:
        -----------
        scope : Construct
            The parent Construct instantiating this construct.
        construct_id : str
            The identifier of this construct.
        jumpstart_model_id : str
            The ID of the JumpStart model to use.
            For available models, see:
            https://sagemaker.readthedocs.io/en/stable/doc_utils/pretrainedmodels.html
        jumpstart_model_region : str
            The region to take the JumpStart model assets from. This may or may not
            be the same region of this construct/endpoint.
        jumpstart_model_version :
            The version of the JumpStart model to use. Use "*" for latest version.
        jumpstart_model_environment : dict
            The environment variables to pass to the model container.
        instance_type : str
            The instance type to use for inference.
        max_capacity : int
            The maximum instance capacity for scaling the endpoint.

        """
        super().__init__(scope, construct_id)
        # pylint: disable=duplicate-code
        self.bucket = s3.Bucket(
            scope=self,
            id=construct_id + "Bucket",
            access_control=s3.BucketAccessControl.PRIVATE,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            event_bridge_enabled=False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=aws_cdk.Duration.days(1),
                    enabled=True,
                    expiration=aws_cdk.Duration.days(30),
                )
            ],
            public_read_access=False,
        )
        ssm.StringParameter(
            scope=self,
            id=construct_id + "bucketNameParameter",
            string_value=self.bucket.bucket_name,
            parameter_name=f'/simple-gen-ai-service/{config["CONFIG"]["repository_name"]}/bucketName',
        )

        self.role = self.create_model_execution_role(bucket=self.bucket)

        self.model = self.create_jumpstart_model(
            construct_id=construct_id + "Model",
            jumpstart_model_id=jumpstart_model_id,
            jumpstart_model_version=jumpstart_model_version,
            jumpstart_model_region=jumpstart_model_region,
            jumpstart_model_environment=jumpstart_model_environment,
            inference_instance_type=instance_type,
            role=self.role,
        )
        if not self.model.model_name:
            raise ValueError("Model name is not defined.")

        self.error_topic = sns.Topic(
            scope=self,
            id=construct_id + "ErrorTopic",
            display_name="errors-" + self.model.model_name,
        )
        self.error_topic.grant_publish(grantee=self.role)
        self.error_topic.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["sns:Publish"],
                effect=iam.Effect.DENY,
                resources=[self.error_topic.topic_arn],
                conditions={
                    "Bool": {
                        "aws:SecureTransport": "false",
                    }
                },
                principals=[iam.AnyPrincipal()],
            )
        )

        self.success_topic = sns.Topic(
            scope=self,
            id=construct_id + "SuccessTopic",
            display_name="success-" + self.model.model_name,
        )
        self.success_topic.grant_publish(grantee=self.role)
        self.success_topic.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["sns:Publish"],
                effect=iam.Effect.DENY,
                resources=[self.success_topic.topic_arn],
                conditions={
                    "Bool": {
                        "aws:SecureTransport": "false",
                    }
                },
                principals=[iam.AnyPrincipal()],
            )
        )

        production_variant = create_production_variant(
            model_name=self.model.model_name,
            instance_type=instance_type,
        )
        async_inference_config = create_async_inference_config(
            bucket_name=self.bucket.bucket_name,
            error_topic=self.error_topic,
            success_topic=self.success_topic,
        )
        endpoint_configuration = self.create_endpoint_configuration(
            construct_id=construct_id + "EndpointConfiguration",
            model=self.model.model,
            production_variant=production_variant,
            async_inference_config=async_inference_config,
        )

        if not endpoint_configuration.endpoint_config_name:
            raise ValueError("Endpoint configuration name is not defined.")
        self.endpoint = cdk_sagemaker.CfnEndpoint(
            scope=self,
            id=construct_id + "Endpoint",
            endpoint_name="ep-" + self.model.model_name,
            endpoint_config_name=endpoint_configuration.endpoint_config_name,
        )
        self.endpoint.node.add_dependency(endpoint_configuration)

        if not self.endpoint.endpoint_name:
            raise ValueError("Endpoint name is not defined.")
        ssm.StringParameter(
            scope=self,
            id=construct_id + "endpointNameParameter",
            string_value=self.endpoint.endpoint_name,
            parameter_name=f'/simple-gen-ai-service/{config["CONFIG"]["repository_name"]}/endpointName',
        )

        self.scaling_policy = self.create_scaling_policy(
            construct_id=construct_id + "ScalingPolicy",
            endpoint=self.endpoint,
            production_variant=production_variant,
            max_capacity=max_capacity,
        )
