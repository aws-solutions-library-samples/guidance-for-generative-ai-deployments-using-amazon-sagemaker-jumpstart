"""
Service Pipeline Stack

This stack includes everything necessary for building and deploying a Text to Image service
on AWS. It includes a CI/CD pipeline based on CDK Pipelines. The service is deployed in stages
which are defined and included separately.
"""

import os
import aws_cdk as cdk
import aws_cdk.aws_codebuild as codebuild
import aws_cdk.aws_codecommit as codecommit
import aws_cdk.aws_iam as iam
from aws_cdk import pipelines
import cdk_nag
import constructs
from simple_generative_ai_service.service_stage import ServiceStage
from .config import config


class ServicePipelineStack(cdk.Stack):
    """
    Stack Class. See description in module docstring.
    """

    def add_cdk_nag_suppressions(self) -> None:
        """
        Add suppressions for CDK Nag rules.
        """
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            (
                f"/{config['CONFIG']['repository_name']}ServiceStack/"
                "Pipeline/Pipeline/ArtifactsBucket/Resource"
            ),
            [
                {
                    "id": "AwsSolutions-S1",
                    "reason": "Artifacts bucket does not need server access logs",
                },
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            (
                f"/{config['CONFIG']['repository_name']}ServiceStack/"
                "Pipeline/Pipeline/Role/DefaultPolicy/Resource"
            ),
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Pipeline may have these wildcard permissions",
                    "appliesTo": [
                        "Action::s3:Abort*",
                        "Action::s3:DeleteObject*",
                        "Action::s3:GetBucket*",
                        "Action::s3:GetObject*",
                        "Action::s3:List*",
                        "Resource::<PipelineArtifactsBucketAEA9A052.Arn>/*",
                    ],
                },
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            (
                f"/{config['CONFIG']['repository_name']}ServiceStack/"
                "Pipeline/Pipeline/Source/CodeCommit/"
                "CodePipelineActionRole/DefaultPolicy/Resource"
            ),
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CodePipelineActionRole may have these wildcard permissions",
                    "appliesTo": [
                        "Action::s3:Abort*",
                        "Action::s3:DeleteObject*",
                        "Action::s3:GetBucket*",
                        "Action::s3:GetObject*",
                        "Action::s3:List*",
                        "Resource::<PipelineArtifactsBucketAEA9A052.Arn>/*",
                    ],
                },
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            (
                f"/{config['CONFIG']['repository_name']}ServiceStack/"
                "Pipeline/Pipeline/Build/Synth/"
                "CdkBuildProject/Role/DefaultPolicy/Resource"
            ),
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "BuildProject role may have these wildcard permissions",
                    "appliesTo": [
                        (
                            f"Resource::arn:aws:logs:{config['CONFIG']['region']}:<AWS::AccountId>:log-group:"
                            "/aws/codebuild/<PipelineBuildSynthCdkBuildProject6BEFA8E6>:*"
                        ),
                        (
                            f"Resource::arn:aws:codebuild:{config['CONFIG']['region']}:<AWS::AccountId>:"
                            "report-group/<PipelineBuildSynthCdkBuildProject6BEFA8E6>-*"
                        ),
                        "Resource::arn:aws:ssm:*:*:parameter/StableDiffusionService*",
                        "Resource::arn:aws:s3:::jumpstart-*",
                        "Resource::arn:aws:s3:::sagemaker-*",
                        "Action::s3:Abort*",
                        "Action::s3:DeleteObject*",
                        "Action::s3:GetBucket*",
                        "Action::s3:GetObject*",
                        "Action::s3:List*",
                        "Resource::<PipelineArtifactsBucketAEA9A052.Arn>/*",
                    ],
                },
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            (
                f"/{config['CONFIG']['repository_name']}ServiceStack/"
                "Pipeline/Pipeline/Build/Synth/CdkBuildProject/Resource"
            ),
            [
                {
                    "id": "AwsSolutions-CB3",
                    "reason": "BuildProject may run privileged",
                },
                {
                    "id": "AwsSolutions-CB4",
                    "reason": "No KMS key required here",
                },
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            (
                f"/{config['CONFIG']['repository_name']}ServiceStack/Pipeline/UpdatePipeline/"
                "SelfMutation/Role/DefaultPolicy/Resource"
            ),
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "SelfMutation role may have these wildcards.",
                    "appliesTo": [
                        (
                            f"Resource::arn:aws:logs:{config['CONFIG']['region']}:<AWS::AccountId>:"
                            "log-group:/aws/codebuild/"
                            "<PipelineUpdatePipelineSelfMutationDAA41400>:*"
                        ),
                        (
                            f"Resource::arn:aws:codebuild:{config['CONFIG']['region']}:<AWS::AccountId>:"
                            "report-group/<PipelineUpdatePipelineSelfMutationDAA41400>-*"
                        ),
                        "Resource::arn:aws:ssm:*:*:parameter/StableDiffusionService*",
                        "Resource::arn:aws:s3:::jumpstart-*",
                        "Resource::arn:aws:s3:::sagemaker-*",
                        "Resource::arn:*:iam::<AWS::AccountId>:role/*",
                        "Resource::*",
                        "Action::s3:GetBucket*",
                        "Action::s3:GetObject*",
                        "Action::s3:List*",
                        "Resource::<PipelineArtifactsBucketAEA9A052.Arn>/*",
                    ],
                },
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            (
                f"/{config['CONFIG']['repository_name']}ServiceStack/"
                "Pipeline/UpdatePipeline/SelfMutation/Resource"
            ),
            [
                {
                    "id": "AwsSolutions-CB3",
                    "reason": "SelfMutation may run privileged",
                },
                {
                    "id": "AwsSolutions-CB4",
                    "reason": "No KMS key required here",
                },
            ],
        )

        if not (
            "INITIAL_DEPLOY" in os.environ and os.environ["INITIAL_DEPLOY"] == "yes"
        ):
            # The INITIAL_DEPLOY mode eliminates the requirement of having
            # docker installed and running on the developer machine. The
            # repository and pipeline in an initial state can be deployed
            # while all steps requiring docker run in CodeBuild.
            cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
                self,
                (
                    f"/{config['CONFIG']['repository_name']}ServiceStack/"
                    "Pipeline/Assets/FileRole/DefaultPolicy/Resource"
                ),
                [
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "Assets role may have these wildcards.",
                        "appliesTo": [
                            (
                                f"Resource::arn:aws:logs:{config['CONFIG']['region']}:"
                                "<AWS::AccountId>:log-group:/aws/codebuild/*"
                            ),
                            f"Resource::arn:aws:codebuild:{config['CONFIG']['region']}:<AWS::AccountId>:report-group/*",
                            "Resource::*",
                            "Resource::arn:aws:ssm:*:*:parameter/StableDiffusionService*",
                            "Resource::arn:aws:s3:::jumpstart-*",
                            "Resource::arn:aws:s3:::sagemaker-*",
                            "Action::s3:GetBucket*",
                            "Action::s3:GetObject*",
                            "Action::s3:List*",
                            "Resource::<PipelineArtifactsBucketAEA9A052.Arn>/*",
                        ],
                    },
                ],
            )
            for file_asset_number in range(1, 5):
                cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
                    self,
                    (
                        f"/{config['CONFIG']['repository_name']}ServiceStack/"
                        f"Pipeline/Assets/FileAsset{file_asset_number}/Resource"
                    ),
                    [
                        {
                            "id": "AwsSolutions-CB4",
                            "reason": "No KMS key required here",
                        },
                    ],
                )
                cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
                    self,
                    (
                        f"/{config['CONFIG']['repository_name']}ServiceStack/"
                        f"Pipeline/Assets/FileAsset{file_asset_number}/Resource"
                    ),
                    [
                        {
                            "id": "AwsSolutions-CB3",
                            "reason": "Build Project builds Docker image.",
                        },
                    ],
                )
                cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
                    self,
                    (
                        f"/{config['CONFIG']['repository_name']}ServiceStack/"
                        "Pipeline/Pipeline/BeforeDeploy/StripAssetsFromAssembly/StripAssetsFromAssembly/"
                        "Role/DefaultPolicy/Resource"
                    ),
                    [
                        {
                            "id": "AwsSolutions-IAM5",
                            "reason": "StripAssetsFromAssembly role may have these wildcards.",
                            "appliesTo": [
                                (
                                    f"Resource::arn:aws:logs:{config['CONFIG']['region']}:<AWS::AccountId>:log-group:/aws/"
                                    "codebuild/<PipelineBeforeDeployStripAssetsFromAssembly3F789918>:*"
                                ),
                                (
                                    f"Resource::arn:aws:codebuild:{config['CONFIG']['region']}:<AWS::AccountId>:"
                                    "report-group/<PipelineBeforeDeployStripAssetsFromAssembly3F789918>-*"
                                ),
                                "Resource::arn:aws:s3:::jumpstart-*",
                                "Resource::arn:aws:s3:::sagemaker-*",
                                "Action::s3:Abort*",
                                "Action::s3:DeleteObject*",
                                "Action::s3:GetBucket*",
                                "Action::s3:GetObject*",
                                "Action::s3:List*",
                                "Resource::<PipelineArtifactsBucketAEA9A052.Arn>/*",
                            ],
                        },
                    ],
                )
            cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
                self,
                (
                    f"/{config['CONFIG']['repository_name']}ServiceStack/Pipeline/Pipeline/"
                    "BeforeDeploy/StripAssetsFromAssembly/StripAssetsFromAssembly/Resource"
                ),
                [
                    {
                        "id": "AwsSolutions-CB3",
                        "reason": "SelfMutation may run privileged",
                    },
                    {
                        "id": "AwsSolutions-CB4",
                        "reason": "No KMS key required here",
                    },
                ],
            )

    def __init__(
        self,
        scope: constructs.Construct,
        construct_id: str,
        repository: codecommit.Repository,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        repository_source = pipelines.CodePipelineSource.code_commit(
            repository,
            branch=config["CONFIG"]["repository_branch"],
        )

        codebuild_role_policies = [
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject"],
                resources=["arn:aws:s3:::sagemaker-*", "arn:aws:s3:::jumpstart-*"],
            ),
        ]
        code_build_defaults = pipelines.CodeBuildOptions(
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.MEDIUM,
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                privileged=True,  # See: https://github.com/aws/aws-cdk/issues/9217
            ),
            role_policy=codebuild_role_policies,
        )

        install_commands = [
            "npm install -g aws-cdk",
            "curl -sSL https://install.python-poetry.org | python3 -",
            "~/.local/share/pypoetry/venv/bin/poetry install",
        ]
        commands = ["~/.local/share/pypoetry/venv/bin/poetry run cdk synth"]

        pipeline = pipelines.CodePipeline(
            scope=self,
            id="Pipeline",
            pipeline_name=f'{config["CONFIG"]["repository_name"]}ServicePipeline',
            code_build_defaults=code_build_defaults,
            docker_enabled_for_self_mutation=True,
            docker_enabled_for_synth=True,
            synth=pipelines.ShellStep(
                "Synth",
                input=repository_source,
                install_commands=install_commands,
                commands=commands,
            ),
        )

        if not (
            "INITIAL_DEPLOY" in os.environ and os.environ["INITIAL_DEPLOY"] == "yes"
        ):
            # The INITIAL_DEPLOY mode eliminates the requirement of having
            # docker installed and running on the developer machine. The
            # repository and pipeline in an initial state can be deployed
            # while all steps requiring docker run in CodeBuild.

            # https://github.com/aws/aws-cdk/issues/9917#issuecomment-1063857885
            strip_assets_step = pipelines.CodeBuildStep(
                id="StripAssetsFromAssembly",
                input=pipeline.cloud_assembly_file_set,
                commands=[
                    'S3_PATH=${CODEBUILD_SOURCE_VERSION#"arn:aws:s3:::"}',
                    "ZIP_ARCHIVE=$(basename $S3_PATH)",
                    "rm -rfv asset.*",
                    "zip -r -q -A $ZIP_ARCHIVE *",
                    "aws s3 cp $ZIP_ARCHIVE s3://$S3_PATH",
                ],
            )
            pipeline.add_wave("BeforeDeploy", pre=[strip_assets_step])

            pipeline.add_stage(
                ServiceStage(
                    self,
                    f'{config["CONFIG"]["repository_name"]}Test',
                )
            )
            pipeline.build_pipeline()
            pipeline.pipeline.artifact_bucket.grant_write(strip_assets_step.project)
        else:
            pipeline.build_pipeline()
        self.add_cdk_nag_suppressions()
