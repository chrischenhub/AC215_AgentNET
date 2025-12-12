#!/bin/bash
# AgentNET Deployment Script
# Usage: ./deploy.sh [images|k8s|all]
# Default: all (deploys both images and k8s)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/app"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

deploy_images() {
    log_info "Deploying images..."
    cd "${APP_DIR}/deploy_images"
    pulumi up --stack dev --refresh -y
    log_info "Images deployed successfully!"
}

deploy_k8s() {
    log_info "Deploying Kubernetes resources..."
    cd "${APP_DIR}/deploy_k8s"
    pulumi up --stack dev --refresh -y
    log_info "Kubernetes resources deployed successfully!"
}

show_status() {
    log_info "Checking deployment status..."
    kubectl get pods -n agentnet-namespace
    echo ""
    kubectl get services -n agentnet-namespace
}

show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  images    Deploy Docker images only"
    echo "  k8s       Deploy Kubernetes resources only"
    echo "  all       Deploy both images and k8s (default)"
    echo "  status    Show current deployment status"
    echo "  logs      Show API pod logs"
    echo "  help      Show this help message"
}

show_logs() {
    log_info "Fetching API pod logs..."
    kubectl logs -n agentnet-namespace -l app=agentnet-api --tail=100
}

# Main
case "${1:-all}" in
    images)
        deploy_images
        ;;
    k8s)
        deploy_k8s
        ;;
    all)
        deploy_images
        deploy_k8s
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        log_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
