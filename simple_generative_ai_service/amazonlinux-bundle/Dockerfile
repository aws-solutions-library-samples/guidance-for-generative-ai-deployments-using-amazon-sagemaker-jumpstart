# Dockerfile for Amazon Linux 2 with all necessary tools for budnling.
FROM public.ecr.aws/amazonlinux/amazonlinux:2023

RUN yum update -y && yum install -y \
shadow-utils \
python3 \
gzip \
tar && \
useradd user

RUN mkdir /{asset-input,asset-output}
RUN chown user /{asset-input,asset-output}

USER user

HEALTHCHECK NONE
