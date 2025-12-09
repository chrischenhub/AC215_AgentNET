import pulumi
import pulumi_gcp as gcp


def create_network(region, app_name):
    # Create VPC network with manual subnet configuration for the cheese app
    network = gcp.compute.Network(
        f"{app_name}-vpc",
        name=f"{app_name}-vpc",
        auto_create_subnetworks=False,
        routing_mode="REGIONAL",
        description="VPC for Kubernetes Cluster",
    )

    # Create subnet within the VPC with private Google access enabled
    subnet = gcp.compute.Subnetwork(
        f"{app_name}-subnet",
        name=f"{app_name}-subnet",
        ip_cidr_range="10.0.0.0/19",
        region=region,
        network=network.id,
        private_ip_google_access=True,
        description="subnet /19 starting after 10.0.0.0/19",
        opts=pulumi.ResourceOptions(depends_on=[network]),
    )

    # Create Cloud Router to enable NAT for private instances
    router = gcp.compute.Router(
        f"{app_name}-router",
        name=f"{app_name}-router",
        network=network.id,
        region=region,
        opts=pulumi.ResourceOptions(depends_on=[network, subnet]),
    )

    # Configure Cloud NAT to allow private instances to access the internet
    nat = gcp.compute.RouterNat(
        f"{app_name}-nat",
        name=f"{app_name}-nat",
        router=router.name,
        region=region,
        nat_ip_allocate_option="AUTO_ONLY",
        source_subnetwork_ip_ranges_to_nat="ALL_SUBNETWORKS_ALL_IP_RANGES",
        log_config=gcp.compute.RouterNatLogConfigArgs(
            enable=True, filter="ERRORS_ONLY"
        ),
        opts=pulumi.ResourceOptions(depends_on=[router]),
    )

    return network, subnet, router, nat
