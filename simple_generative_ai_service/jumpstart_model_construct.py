"""
An AWS CDK v2 Level 2Construct for Amazon SageMaker JumpStart models.
"""

import os
from hashlib import md5
from typing import Union

import aws_cdk
import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3_assets as s3_assets
import aws_cdk.aws_sagemaker as cdk_sagemaker
import boto3
import constructs
from sagemaker import image_uris, model_uris, script_uris


MAX_MODEL_NAME_SIZE = 63
MODEL_NAME_HASH_SIZE = 8
MODEL_NAME_PREFIX_SIZE = MAX_MODEL_NAME_SIZE - MODEL_NAME_HASH_SIZE


s3 = boto3.client("s3")


def container_uri_to_repo_arn(uri: str) -> str:
    """
    Extract the ecr repository ARN out of the given container image URI.
    Example image_uri:
    763104351884.dkr.ecr.eu-central-1.amazonaws.com/huggingface-pytorch
        -inference:1.10.2-transformers4.17.0-gpu-py38-cu113-ubuntu20.04

    Parameters
    ----------
    uri : str
        The container image URI.

    Returns
    -------
    str
        The ecr repository ARN.
    """
    left, right = uri.split("/")
    repo_account_id, _, _, repo_region, _, _ = left.split(".")
    repo_name = right.split(":")[0]
    return f"arn:aws:ecr:{repo_region}:{repo_account_id}:repository/{repo_name}"


class JumpStartModel(constructs.Construct):
    """
    An Amazon SageMaker Model class, based on the given SageMaker JumpStart model.
    This class uses the Sagemaker SDK to identify the necessary components and
    builds its own set of artifacts to instantiate a CDK Model class.

    """

    def create_model_asset(
        self,
        asset_id: str,
        jumpstart_model_id: str,
        jumpstart_model_region: str,
        jumpstart_model_version: str = "*",
    ) -> s3_assets.Asset:
        """
        Create a model.tar.gz file for use in a Sagemaker model.

        Parameters
        ----------
        asset_id : str
            The ID of the asset.
        jumpstart_model_id : str
            The ID of the SageMaker JumpStart model.
        jumpstart_model_version : str
            The version of the JumpStart model. "*" selects that latest.
        jumpstart_model_region : str
            The AWS region of the JumpStart model.

        Returns
        -------
        Asset
            The CDK V2 Asset containing bundled model artifacts and inference code.
        """
        # This yields an S3 URI with code that should go into the code folder inside
        # the final model.tar.gz file.
        model_inference_code_uri = script_uris.retrieve(
            region=jumpstart_model_region,
            model_id=jumpstart_model_id,
            model_version=jumpstart_model_version,
            script_scope="inference",
        )

        # Generate an S3 pre-signed URL to feed into Docker when asset bundling.
        _, _, bucket, key = model_inference_code_uri.split("/", maxsplit=3)
        model_inference_code_presigned_url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
        )

        # This yields an S3 URI with the actual model data.
        model_uri = model_uris.retrieve(
            region=jumpstart_model_region,
            model_id=jumpstart_model_id,
            model_version=jumpstart_model_version,
            model_scope="inference",
        )

        # Generate an S3 pre-signed URL for the model to feed into Docker when
        # asset bundling.
        _, _, bucket, key = model_uri.split("/", maxsplit=3)
        model_presigned_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=3600,
        )

        return s3_assets.Asset(
            scope=self,
            id=asset_id,
            # /asset-input and working directory in the container
            path=os.path.join(os.path.dirname(__file__), "asset-input"),
            bundling=aws_cdk.BundlingOptions(
                image=aws_cdk.DockerImage.from_build(
                    os.path.join(os.path.dirname(__file__), "amazonlinux-bundle")
                ),
                entrypoint=["/bin/sh", "-c"],
                command=["/usr/bin/bash ./bundle_asset.sh"],
                environment={
                    "MODEL_INFERENCE_CODE_URL": model_inference_code_presigned_url,
                    "MODEL_URL": model_presigned_url,
                },
                output_type=aws_cdk.BundlingOutput.ARCHIVED,
            ),
        )

    def create_model(  # pylint: disable=too-many-arguments
        self,
        model_id: str,
        model_data_asset: s3_assets.Asset,
        role: iam.Role,
        model_container_uri: str,
        model_container_environment: Union[dict, None] = None,
    ) -> cdk_sagemaker.CfnModel:
        """
        Create the SageMaker Model based on the given parameters.

        Parameters:
        -----------
        model_id : str
            The AWS CDK scoped id of this resource.
        model_container_uri : str
            The Docker container uri to use for this model.
        model_container_environment : dict
            A dict with environment variables for the Docker container.
        model_data_asset : Asset
            The CDK V2 S3 Asset containing the model data.
        role : Role
            The CDK V2 IAM Role to assume when executing the model.

        Returns
        -------
        CfnModel
            A CDK V2 SageMaker JumpStart CfnModel.
        """
        # Define the container to run the model in.
        # See also: https://towardsdatascience.com/
        #               deploying-sagemaker-endpoints-with-cloudformation-b43f7d495640
        # See also: https://docs.aws.amazon.com/sagemaker/latest/dg/
        #               neo-deployment-hosting-services-cli.html
        container_definition_property = (
            cdk_sagemaker.CfnModel.ContainerDefinitionProperty(
                container_hostname=None,
                environment=model_container_environment,
                image=model_container_uri,
                image_config=cdk_sagemaker.CfnModel.ImageConfigProperty(
                    repository_access_mode="Platform"
                ),
                inference_specification_name=None,
                mode="SingleModel",
                model_data_url=model_data_asset.s3_object_url,
                model_package_name=None,
                multi_model_config=None,
            )
        )

        # Use the arguments to construct a unique model name with a hash to make
        # CloudFormation happy.
        hash_input = (
            model_id
            + model_container_uri
            + str(model_container_environment)
            + model_data_asset.s3_object_url
            + role.role_id
        ).encode("utf-8")
        model_name_hash = md5(  # nosec nosemgrep
            hash_input, usedforsecurity=False
        ).hexdigest()
        model_name = (
            model_id[-MODEL_NAME_PREFIX_SIZE:] + model_name_hash[-MODEL_NAME_HASH_SIZE]
        )

        # Build the SageMaker model.
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sagemaker/CfnModel.html
        model = cdk_sagemaker.CfnModel(
            scope=self,
            id=model_id,
            execution_role_arn=role.role_arn,
            containers=None,  # Single container, see below: primary_container.
            enable_network_isolation=False,
            inference_execution_config=None,
            model_name=model_name,
            primary_container=container_definition_property,
            tags=None,
            vpc_config=None,
        )

        role.add_to_policy(
            statement=iam.PolicyStatement(
                # See: https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html#
                #      sagemaker-roles-createmodel-perms
                actions=[
                    "cloudwatch:PutMetricData",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:CreateLogGroup",
                    "logs:DescribeLogStreams",
                    "ecr:GetAuthorizationToken",
                ],
                resources=["*"],
            )
        )

        model_repo_arn = container_uri_to_repo_arn(uri=model_container_uri)
        role.add_to_policy(
            statement=iam.PolicyStatement(
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                ],
                resources=[model_repo_arn],
            )
        )

        model_data_asset.grant_read(grantee=role)

        return model

    def __init__(  # pylint: disable=too-many-arguments
        self,
        scope: constructs.Construct,
        construct_id: str,
        role: iam.Role,
        inference_instance_type: str,
        jumpstart_model_id: str,
        jumpstart_model_region: str,
        jumpstart_model_version: str = "*",
        container_environment: Union[dict, None] = None,
    ) -> None:
        """
        Initialize this JumpStartModel class.

        Parameters:
        -----------
        scope : Construct
            The parent Construct instantiating this construct.
        construct_id : str
            The identifier of this construct.
        role : Role
            The IAM role to use for the model.
        inference_instance_type : str
            The instance type to use for inference.
        jumpstart_model_id : str
            The ID of the JumpStart model to use.
            For available models, see:
            https://sagemaker.readthedocs.io/en/stable/doc_utils/pretrainedmodels.html
        jumpstart_model_region : str
            The region of the JumpStart model to use.
        jumpstart_model_version :
            The version of the JumpStart model to use. Use "*" for latest version.
        container_environment : dict
            The environment variables to pass to the model container.
        """
        super().__init__(scope, construct_id)

        self.asset = self.create_model_asset(
            asset_id=construct_id + "Asset",
            jumpstart_model_id=jumpstart_model_id,
            jumpstart_model_version=jumpstart_model_version,
            jumpstart_model_region=jumpstart_model_region,
        )

        model_container_uri = image_uris.retrieve(
            region=jumpstart_model_region,
            framework=None,  # automatically inferred from model_id
            image_scope="inference",
            model_id=jumpstart_model_id,
            model_version=jumpstart_model_version,
            instance_type=inference_instance_type,
        )

        model_id = construct_id + "Model"
        self.model = self.create_model(
            model_id=model_id,
            model_container_uri=model_container_uri,
            model_container_environment=container_environment,
            model_data_asset=self.asset,
            role=role,
        )

        # Expose some of the model's attributes to the outside world.
        self.model_name = self.model.model_name

        # Add a dependency on the role because CloudFormation checks for it to
        # be fully capable of accessing all data at model creation time.
        self.model.node.add_dependency(role)
