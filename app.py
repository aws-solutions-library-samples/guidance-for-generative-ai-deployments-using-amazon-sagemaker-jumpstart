#!/usr/bin/env python3
"""
This script is the entrypoint for the Text To Image Service cdk project.
"""

import aws_cdk as cdk
import cdk_nag
from simple_generative_ai_service.service_pipeline_stack import (
    ServicePipelineStack,
)
from simple_generative_ai_service.repo_stack import RepositoryStack
from simple_generative_ai_service.config import config

app: cdk.App = cdk.App()
cdk.Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(verbose=True))

repository_stack = RepositoryStack(
    scope=app,
    construct_id=f'{config["CONFIG"]["repository_name"]}RepositoryStack',
    env={"region": config["CONFIG"]["region"]},
    description="Guidance for Image Generation on AWS (SO9234)",
)

ServicePipelineStack(
    scope=app,
    construct_id=f'{config["CONFIG"]["repository_name"]}ServiceStack',
    repository=repository_stack.repository,
    env={"region": config["CONFIG"]["region"]},
    description="Guidance for Image Generation on AWS (SO9234)",
)

app.synth()
