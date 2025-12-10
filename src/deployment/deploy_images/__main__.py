import datetime

import pulumi
import pulumi_docker_build as docker_build
from pulumi import CustomTimeouts

# Required config/inputs
project = pulumi.Config("gcp").require("project")
repository_name = "agentnet-repository"
registry_url = f"us-central1-docker.pkg.dev/{project}/{repository_name}"

# Timestamp tag so every build is unique
timestamp_tag = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

# Build & push the AgentNET API image using the Dockerfile that already exists in src/models.
# The deployment docker-shell mounts the whole src tree at /workspace.
# The Dockerfile expects the build context to be at src/ level (uses paths like "src/models/...").
context_path = "/workspace"
dockerfile_path = "/workspace/models/Dockerfile"

api_service_image = docker_build.Image(
    "build-agentnet-api-service",
    tags=[
        pulumi.Output.concat(registry_url, "/agentnet-api-service:", timestamp_tag)
    ],
    context=docker_build.BuildContextArgs(location=context_path),
    dockerfile={"location": dockerfile_path},
    platforms=[docker_build.Platform.LINUX_AMD64],
    push=True,
    opts=pulumi.ResourceOptions(
        custom_timeouts=CustomTimeouts(create="30m"),
        retain_on_delete=True,
    ),
)

frontend_dockerfile_path = "/workspace/frontend-simple/Dockerfile"
frontend_image = docker_build.Image(
    "build-agentnet-frontend",
    tags=[
        pulumi.Output.concat(registry_url, "/agentnet-frontend:", timestamp_tag)
    ],
    context=docker_build.BuildContextArgs(location="/workspace/frontend-simple"),
    dockerfile={"location": frontend_dockerfile_path},
    platforms=[docker_build.Platform.LINUX_AMD64],
    push=True,
    opts=pulumi.ResourceOptions(
        custom_timeouts=CustomTimeouts(create="30m"),
        retain_on_delete=True,
    ),
)

# Export references to stack
pulumi.export("agentnet-api-service-ref", api_service_image.ref)
pulumi.export("agentnet-api-service-tags", api_service_image.tags)
pulumi.export("agentnet-frontend-ref", frontend_image.ref)
pulumi.export("agentnet-frontend-tags", frontend_image.tags)
