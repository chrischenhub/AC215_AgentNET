import pulumi
import pulumi_gcp as gcp
from pulumi import StackReference, ResourceOptions, Output
import pulumi_kubernetes as k8s

from create_network import create_network
from create_cluster import create_cluster
from setup_containers import setup_containers
from setup_loadbalancer import setup_loadbalancer
from setup_loadbalancer_ssl import setup_loadbalancer_ssl

# Get project info and configuration
gcp_config = pulumi.Config("gcp")
project = gcp_config.get("project")
region = "us-central1"
app_name = "agentnet"

# Check if SSL is enabled
deploy_config = pulumi.Config("deploy-k8s")
setupSSL = deploy_config.get_bool("setupSSL") or False

# Create the required network setups
network, subnet, router, nat = create_network(region, app_name)

# Create & Setup Cluster
cluster, namespace, k8s_provider, ksa_name = create_cluster(
    project, region, network, subnet, app_name
)

# Setup Containers (API + Frontend for AgentNET)
frontend_service, api_service = setup_containers(
    project, namespace, k8s_provider, ksa_name, app_name
)

# Setup Load Balancer (with or without SSL)
if setupSSL:
    ip_address, ingress, host = setup_loadbalancer_ssl(
        namespace, k8s_provider, frontend_service, api_service, app_name
    )
else:
    ip_address, ingress, host = setup_loadbalancer(
        namespace, k8s_provider, frontend_service, api_service, app_name
    )

# Export values
pulumi.export("cluster_name", cluster.name)
pulumi.export("cluster_endpoint", cluster.endpoint)
pulumi.export("kubeconfig", k8s_provider.kubeconfig)
pulumi.export("namespace", namespace.metadata.name)
pulumi.export("ingress_name", ingress.metadata.name)
pulumi.export("ip_address", ip_address)
pulumi.export("app_url", host.apply(lambda domain: f"http{'s' if setupSSL else ''}://{domain}"))
