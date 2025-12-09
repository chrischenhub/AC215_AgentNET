import pulumi
import pulumi_gcp as gcp
from pulumi import StackReference, ResourceOptions, Output
import pulumi_kubernetes as k8s


def setup_containers(project, namespace, k8s_provider, ksa_name, app_name):
    """
    Setup the AgentNET API service container.

    AgentNET is a single-service application that includes:
    - FastAPI app with RAG search for MCP server recommendations
    - Agent workflow execution with OpenAI
    - Web UI (Jinja2 templates)
    - Embedded Chroma vector DB with GCS sync
    """

    # Get image reference from deploy_images stack
    # For local backend, use: "organization/deploy-images/dev"
    images_stack = pulumi.StackReference("organization/deploy-images/dev")
    api_service_tag = images_stack.get_output("agentnet-api-service-tags")

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
                            image=api_service_tag.apply(lambda tags: tags[0]),
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

    return api_service
