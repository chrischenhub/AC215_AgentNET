import pulumi
import pulumi_gcp as gcp
from pulumi import StackReference, ResourceOptions, Output
import pulumi_kubernetes as k8s


def setup_loadbalancer(namespace, k8s_provider, api_service, app_name):
    """
    Setup Nginx Ingress Controller and Ingress resource for AgentNET.

    Routes all traffic to the single AgentNET API service which serves:
    - Web UI at /
    - API endpoints at /api/*
    """

    # Nginx Ingress Controller using Helm
    nginx_helm = k8s.helm.v3.Release(
        "nginx-f5",
        chart="nginx-ingress",
        version="2.3.1",
        namespace=namespace.metadata.name,
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo="https://helm.nginx.com/stable"
        ),
        values={
            "controller": {
                "service": {
                    "type": "LoadBalancer",
                },
                "resources": {
                    "requests": {
                        "memory": "128Mi",
                        "cpu": "100m",
                    },
                    "limits": {
                        "memory": "256Mi",
                        "cpu": "200m",
                    },
                },
                "replicaCount": 1,
                "ingressClass": {
                    "name": "nginx",
                    "create": True,
                    "setAsDefaultIngress": True,
                },
            },
        },
        opts=ResourceOptions(provider=k8s_provider),
    )

    # Get the service created by Helm to extract the LoadBalancer IP
    nginx_service = k8s.core.v1.Service.get(
        "nginx-ingress-service",
        pulumi.Output.concat(
            nginx_helm.status.namespace,
            "/",
            nginx_helm.status.name,
            "-nginx-ingress-controller",
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[nginx_helm]),
    )
    ip_address = nginx_service.status.load_balancer.ingress[0].ip
    host = ip_address.apply(lambda ip: f"{ip}.sslip.io")

    # Ingress resource - routes all traffic to AgentNET API service
    ingress = k8s.networking.v1.Ingress(
        f"{app_name}-ingress",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=f"{app_name}-ingress",
            namespace=namespace.metadata.name,
            annotations={
                "ingress.kubernetes.io/ssl-redirect": "false",
            },
        ),
        spec=k8s.networking.v1.IngressSpecArgs(
            ingress_class_name="nginx",
            rules=[
                k8s.networking.v1.IngressRuleArgs(
                    host=host,
                    http=k8s.networking.v1.HTTPIngressRuleValueArgs(
                        paths=[
                            # Route all traffic to the AgentNET API service
                            # The FastAPI app serves both the web UI and API endpoints
                            k8s.networking.v1.HTTPIngressPathArgs(
                                path="/",
                                path_type="Prefix",
                                backend=k8s.networking.v1.IngressBackendArgs(
                                    service=k8s.networking.v1.IngressServiceBackendArgs(
                                        name=api_service.metadata["name"],
                                        port=k8s.networking.v1.ServiceBackendPortArgs(
                                            number=8000
                                        ),
                                    )
                                ),
                            ),
                        ]
                    ),
                )
            ],
        ),
        opts=ResourceOptions(
            provider=k8s_provider,
            depends_on=[nginx_helm],
        ),
    )

    return ip_address, ingress, host
