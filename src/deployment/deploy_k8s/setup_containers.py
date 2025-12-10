import pulumi
import pulumi_gcp as gcp
from pulumi import StackReference, ResourceOptions, Output
import pulumi_kubernetes as k8s


def setup_containers(project, namespace, k8s_provider, ksa_name, app_name):
    """
    Setup the AgentNET API + Frontend containers.

    AgentNET API includes:
    - FastAPI app with RAG search for MCP server recommendations
    - Agent workflow execution with OpenAI
    - Embedded Chroma vector DB with GCS sync
    Frontend ships separately from `src/frontend-simple` as a static container.
    """

    # Get image reference from deploy_images stack (overrideable via config)
    deploy_cfg = pulumi.Config("deploy-k8s")
    images_stack_name = deploy_cfg.get("imagesStack") or "organization/deploy-images/dev"
    api_image_override = deploy_cfg.get("apiImage")
    frontend_image_override = deploy_cfg.get("frontendImage")

    images_stack = pulumi.StackReference(images_stack_name)
    api_service_tag = images_stack.get_output("agentnet-api-service-tags")
    frontend_tag = images_stack.get_output("agentnet-frontend-tags")

    # Resolve images with overrides and friendly errors

    def _first_tag(tags: list[str] | None, label: str) -> str:
        if not tags:
            raise ValueError(
                f"No {label} image tag found. Run deploy_images or set deploy-k8s:{label}Image in config."
            )
        return tags[0]

    api_image = (
        pulumi.Output.from_input(api_image_override)
        if api_image_override
        else api_service_tag.apply(lambda tags: _first_tag(tags, "api"))
    )
    frontend_image = (
        pulumi.Output.from_input(frontend_image_override)
        if frontend_image_override
        else frontend_tag.apply(lambda tags: _first_tag(tags, "frontend"))
    )

    # Persistent storage for Chroma vector DB and application data
    # This will be used to persist embeddings between restarts
    persistent_pvc = k8s.core.v1.PersistentVolumeClaim(
        "agentnet-pvc",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="agentnet-pvc",
            namespace=namespace.metadata.name,
        ),
        spec=k8s.core.v1.PersistentVolumeClaimSpecArgs(
            access_modes=["ReadWriteOnce"],
            resources=k8s.core.v1.VolumeResourceRequirementsArgs(
                requests={"storage": "10Gi"},  # Storage for Chroma embeddings
            ),
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[namespace]),
    )

    # Create a Kubernetes Secret for OPENAI_API_KEY
    # You'll need to set this up manually or via Pulumi config
    # For now, we'll reference it as an environment variable from a secret
    openai_secret = k8s.core.v1.Secret(
        "openai-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="openai-secret",
            namespace=namespace.metadata.name,
        ),
        string_data={
            "OPENAI_API_KEY": pulumi.Config("agentnet").get_secret("openai_api_key") or "",
        },
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[namespace]),
    )

    # AgentNET API Deployment
    api_deployment = k8s.apps.v1.Deployment(
        "agentnet-api",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="agentnet-api",
            namespace=namespace.metadata.name,
        ),
        spec=k8s.apps.v1.DeploymentSpecArgs(
            replicas=1,
            selector=k8s.meta.v1.LabelSelectorArgs(
                match_labels={"app": "agentnet-api"},
            ),
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels={"app": "agentnet-api"},
                ),
                spec=k8s.core.v1.PodSpecArgs(
                    service_account_name=ksa_name,  # Use KSA for Workload Identity (GCP access)
                    security_context=k8s.core.v1.PodSecurityContextArgs(
                        fs_group=1000,
                    ),
                    volumes=[
                        k8s.core.v1.VolumeArgs(
                            name="agentnet-storage",
                            persistent_volume_claim=k8s.core.v1.PersistentVolumeClaimVolumeSourceArgs(
                                claim_name=persistent_pvc.metadata.name,
                            ),
                        ),
                    ],
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name="agentnet-api",
                            image=api_image,
                            image_pull_policy="IfNotPresent",
                            ports=[
                                k8s.core.v1.ContainerPortArgs(
                                    container_port=8000,  # FastAPI default port
                                    protocol="TCP",
                                )
                            ],
                            # Security context for gcsfuse FUSE mounts
                            security_context=k8s.core.v1.SecurityContextArgs(
                                privileged=True,  # Required for FUSE mounts
                            ),
                            volume_mounts=[
                                k8s.core.v1.VolumeMountArgs(
                                    name="agentnet-storage",
                                    mount_path="/app/src/models/GCB",  # Chroma persist directory
                                ),
                            ],
                            env=[
                                # DEV=0 means production mode (run uvicorn server)
                                # DEV=1 would mean development mode (interactive shell)
                                k8s.core.v1.EnvVarArgs(
                                    name="DEV",
                                    value="0",
                                ),
                                # OpenAI API Key from secret
                                k8s.core.v1.EnvVarArgs(
                                    name="OPENAI_API_KEY",
                                    value_from=k8s.core.v1.EnvVarSourceArgs(
                                        secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                                            name=openai_secret.metadata.name,
                                            key="OPENAI_API_KEY",
                                        ),
                                    ),
                                ),
                                # GCS Configuration
                                k8s.core.v1.EnvVarArgs(
                                    name="GCS_BUCKET_NAME",
                                    value="agentnet215",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="GCS_DATA_DIR",
                                    value="mcp_data_json",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="GCS_CHROMA_DIR",
                                    value="chroma_store",
                                ),
                                # GCP Project
                                k8s.core.v1.EnvVarArgs(
                                    name="GCP_PROJECT",
                                    value=project,
                                ),
                                # CORS for split frontend (allow all by default)
                                k8s.core.v1.EnvVarArgs(
                                    name="FRONTEND_ORIGINS",
                                    value="*",
                                ),
                                # Server configuration
                                k8s.core.v1.EnvVarArgs(
                                    name="HOST",
                                    value="0.0.0.0",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="PORT",
                                    value="8000",
                                ),
                            ],
                            working_dir="/app/src/models",
                            resources=k8s.core.v1.ResourceRequirementsArgs(
                                requests={"cpu": "500m", "memory": "2Gi"},
                                limits={"cpu": "1000m", "memory": "4Gi"},
                            ),
                            # Health checks
                            liveness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    path="/",
                                    port=8000,
                                ),
                                initial_delay_seconds=30,
                                period_seconds=10,
                            ),
                            readiness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    path="/",
                                    port=8000,
                                ),
                                initial_delay_seconds=5,
                                period_seconds=5,
                            ),
                        ),
                    ],
                ),
            ),
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[namespace, persistent_pvc, openai_secret]),
    )

    # AgentNET API Service
    api_service = k8s.core.v1.Service(
        "agentnet-api-service",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="agentnet-api",
            namespace=namespace.metadata.name,
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            type="ClusterIP",  # Internal only - exposed via Ingress
            ports=[
                k8s.core.v1.ServicePortArgs(
                    port=8000,
                    target_port=8000,
                    protocol="TCP",
                )
            ],
            selector={"app": "agentnet-api"},
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[api_deployment]),
    )

    # Frontend Deployment (static bundle served via http-server)
    frontend_deployment = k8s.apps.v1.Deployment(
        "agentnet-frontend",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="agentnet-frontend",
            namespace=namespace.metadata.name,
        ),
        spec=k8s.apps.v1.DeploymentSpecArgs(
            replicas=1,
            selector=k8s.meta.v1.LabelSelectorArgs(
                match_labels={"app": "agentnet-frontend"},
            ),
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels={"app": "agentnet-frontend"},
                ),
                spec=k8s.core.v1.PodSpecArgs(
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name="agentnet-frontend",
                            image=frontend_image,
                            image_pull_policy="IfNotPresent",
                            ports=[
                                k8s.core.v1.ContainerPortArgs(
                                    container_port=8080,
                                    protocol="TCP",
                                )
                            ],
                            env=[
                                k8s.core.v1.EnvVarArgs(
                                    name="PORT",
                                    value="8080",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="API_BASE_URL",
                                    value="/api",
                                ),
                            ],
                            resources=k8s.core.v1.ResourceRequirementsArgs(
                                requests={"cpu": "100m", "memory": "256Mi"},
                                limits={"cpu": "250m", "memory": "512Mi"},
                            ),
                        ),
                    ],
                ),
            ),
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[namespace]),
    )

    frontend_service = k8s.core.v1.Service(
        "agentnet-frontend-service",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="agentnet-frontend",
            namespace=namespace.metadata.name,
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            type="ClusterIP",
            ports=[
                k8s.core.v1.ServicePortArgs(
                    port=8080,
                    target_port=8080,
                    protocol="TCP",
                )
            ],
            selector={"app": "agentnet-frontend"},
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[frontend_deployment]),
    )

    # Autoscaling: API HPA (CPU-based)
    api_hpa = k8s.autoscaling.v2.HorizontalPodAutoscaler(
        "agentnet-api-hpa",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="agentnet-api-hpa",
            namespace=namespace.metadata.name,
        ),
        spec=k8s.autoscaling.v2.HorizontalPodAutoscalerSpecArgs(
            scale_target_ref=k8s.autoscaling.v2.CrossVersionObjectReferenceArgs(
                api_version="apps/v1",
                kind="Deployment",
                name=api_deployment.metadata["name"],
            ),
            min_replicas=1,
            max_replicas=5,
            metrics=[
                k8s.autoscaling.v2.MetricSpecArgs(
                    type="Resource",
                    resource=k8s.autoscaling.v2.ResourceMetricSourceArgs(
                        name="cpu",
                        target=k8s.autoscaling.v2.MetricTargetArgs(
                            type="Utilization",
                            average_utilization=70,
                        ),
                    ),
                )
            ],
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[api_deployment]),
    )

    # Autoscaling: Frontend HPA (CPU-based, modest limits)
    frontend_hpa = k8s.autoscaling.v2.HorizontalPodAutoscaler(
        "agentnet-frontend-hpa",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="agentnet-frontend-hpa",
            namespace=namespace.metadata.name,
        ),
        spec=k8s.autoscaling.v2.HorizontalPodAutoscalerSpecArgs(
            scale_target_ref=k8s.autoscaling.v2.CrossVersionObjectReferenceArgs(
                api_version="apps/v1",
                kind="Deployment",
                name=frontend_deployment.metadata["name"],
            ),
            min_replicas=1,
            max_replicas=3,
            metrics=[
                k8s.autoscaling.v2.MetricSpecArgs(
                    type="Resource",
                    resource=k8s.autoscaling.v2.ResourceMetricSourceArgs(
                        name="cpu",
                        target=k8s.autoscaling.v2.MetricTargetArgs(
                            type="Utilization",
                            average_utilization=60,
                        ),
                    ),
                )
            ],
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[frontend_deployment]),
    )

    return frontend_service, api_service
