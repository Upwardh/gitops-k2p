#!/bin/bash

# ArgoCD Installation and Setup Script
# This script installs ArgoCD and configures it for the lb-exporter project

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ARGOCD_VERSION="v2.8.4"
ARGOCD_NAMESPACE="argocd"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Check if kubectl can connect to cluster
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_success "kubectl is available and connected to cluster"
}

install_argocd() {
    log_info "Installing ArgoCD version $ARGOCD_VERSION"
    
    # Create ArgoCD namespace
    kubectl create namespace $ARGOCD_NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
    
    # Install ArgoCD
    kubectl apply -n $ARGOCD_NAMESPACE -f https://raw.githubusercontent.com/argoproj/argo-cd/$ARGOCD_VERSION/manifests/install.yaml
    
    log_info "Waiting for ArgoCD to be ready..."
    kubectl wait --for=condition=available --timeout=600s deployment/argocd-server -n $ARGOCD_NAMESPACE
    
    log_success "ArgoCD installation completed"
}

configure_argocd() {
    log_info "Configuring ArgoCD for lb-exporter project"
    
    # Apply the project and applications
    kubectl apply -f "$PROJECT_ROOT/k8s-manifests/argocd-apps/project.yaml"
    kubectl apply -f "$PROJECT_ROOT/k8s-manifests/argocd-apps/lb-exporter-dev.yaml"
    kubectl apply -f "$PROJECT_ROOT/k8s-manifests/argocd-apps/lb-exporter-staging.yaml"
    kubectl apply -f "$PROJECT_ROOT/k8s-manifests/argocd-apps/lb-exporter-prod.yaml"
    
    log_success "ArgoCD configuration completed"
}

get_admin_password() {
    log_info "Retrieving ArgoCD admin password"
    
    # Get the admin password
    ADMIN_PASSWORD=$(kubectl -n $ARGOCD_NAMESPACE get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
    
    echo
    log_success "ArgoCD Admin Credentials:"
    echo "Username: admin"
    echo "Password: $ADMIN_PASSWORD"
    echo
}

setup_port_forward() {
    log_info "Setting up port forward to ArgoCD server"
    
    # Kill existing port-forward if any
    pkill -f "kubectl port-forward.*argocd-server" || true
    
    # Start port-forward in background
    kubectl port-forward svc/argocd-server -n $ARGOCD_NAMESPACE 8080:443 > /dev/null 2>&1 &
    
    sleep 3
    
    log_success "ArgoCD is accessible at: https://localhost:8080"
    log_info "Use the credentials above to login"
}

install_argocd_cli() {
    log_info "Installing ArgoCD CLI"
    
    # Download and install ArgoCD CLI
    curl -sSL -o /tmp/argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/download/$ARGOCD_VERSION/argocd-linux-amd64
    sudo install -m 555 /tmp/argocd-linux-amd64 /usr/local/bin/argocd
    rm /tmp/argocd-linux-amd64
    
    log_success "ArgoCD CLI installed successfully"
}

show_status() {
    log_info "ArgoCD Status:"
    kubectl get pods -n $ARGOCD_NAMESPACE
    echo
    
    log_info "ArgoCD Applications:"
    kubectl get applications -n $ARGOCD_NAMESPACE
    echo
}

show_help() {
    cat << EOF
ArgoCD Installation and Setup Script

Usage: $0 [ACTION]

ACTION:
    install     Install ArgoCD and configure for lb-exporter
    status      Show ArgoCD status
    password    Get admin password
    port-forward Setup port forward to ArgoCD UI
    cli         Install ArgoCD CLI
    help        Show this help message

Examples:
    $0 install      # Full installation and configuration
    $0 status       # Show current status
    $0 password     # Get admin password
    $0 port-forward # Setup port forward for UI access

EOF
}

# Main execution
main() {
    local action=${1:-install}
    
    case $action in
        install)
            check_kubectl
            install_argocd
            configure_argocd
            get_admin_password
            setup_port_forward
            install_argocd_cli
            show_status
            ;;
        status)
            show_status
            ;;
        password)
            get_admin_password
            ;;
        port-forward)
            setup_port_forward
            ;;
        cli)
            install_argocd_cli
            ;;
        help)
            show_help
            ;;
        *)
            log_error "Invalid action: $action"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"