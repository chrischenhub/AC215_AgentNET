import pulumi
import pulumi_gcp as gcp
from pulumi import StackReference, ResourceOptions, Output
import pulumi_kubernetes as k8s


def setup_loadbalancer_ssl(namespace, k8s_provider, api_service, app_name):
    """
    Setup GKE Ingress with SSL/TLS using Google-managed certificates.

    This uses the GCE Ingress Controller with:
    - Global static IP address
    - Google-managed SSL certificate
    - HTTPS redirect
    """

    # Get a global IP address
    ip_address = gcp.compute.GlobalAddress(
        "global-static-ip",
        name=f"{app_name}-global-ip",
        address_type="EXTERNAL",
        ip_version="IPV4",
    )
    host = ip_address.address.apply(lambda ip: f"{ip}.sslip.io")

    # Create Google-managed SSL Certificate
    managed_cert = k8s.apiextensions.CustomResource(
        "managed-cert",
        api_version="networking.gke.io/v1beta1",
        kind="ManagedCertificate",
        metadata={
            "name": "managed-certificates",
            "namespace": namespace.metadata.name,
        },
        spec={"domains": [host]},
        opts=ResourceOptions(provider=k8s_provider, depends_on=[ip_address]),
    )

    # Frontend Config for HTTPS redirect
    frontend_config = k8s.apiextensions.CustomResource(
        "https-redirect",
        api_version="networking.gke.io/v1",
        kind="FrontendConfig",
        metadata={
            "name": "https-redirect",
            "namespace": namespace.metadata.name,
        },
        spec={"redirectToHttps": {"enabled": True}},
        opts=ResourceOptions(provider=k8s_provider),
    )

    # GKE Ingress with SSL
    ingress = k8s.networking.v1.Ingress(
        f"{app_name}-ingress",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=f"{app_name}-ingress",
            namespace=namespace.metadata.name,
            annotations={
                "kubernetes.io/ingress.global-static-ip-name": ip_address.name,
                "networking.gke.io/managed-certificates": "managed-certificates",
                "networking.gke.io/frontend-config": "https-redirect",
            },
        ),
        spec=k8s.networking.v1.IngressSpecArgs(
            ingress_class_name="gce",  # Use GCE Ingress Controller
            rules=[
                k8s.networking.v1.IngressRuleArgs(
                    host=host,
                    http=k8s.networking.v1.HTTPIngressRuleValueArgs(
                        paths=[
                            # All traffic goes to the AgentNET API service
                            # which serves both web UI and API endpoints
                            k8s.networking.v1.HTTPIngressPathArgs(
                                path="/",
                                path_type="Prefix",
                                backend=k8s.networking.v1.IngressBackendArgs(
                                    service=k8s.networking.v1.IngressServiceBackendArgs(
                                        name=api_service.metadata["name"],
                                        port=k8s.networking.v1.ServiceBackendPortArgs(
                                            number=8000,
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
            depends_on=[managed_cert, frontend_config],
        ),
    )

    return ip_address, ingress, host
