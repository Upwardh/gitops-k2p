#!/bin/bash

# KT Cloud LB Exporter Deployment Script
# Usage: ./deploy.sh [dev|staging|prod] [action]

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
KUSTOMIZE_DIR="$PROJECT_ROOT/k8s-manifests"
ARGOCD_APPS_DIR="$KUSTOMIZE_DIR/argocd-apps"

# Default values
ENVIRONMENT=${1:-dev}
ACTION=${2:-deploy}

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

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    if ! command -v kustomize &> /dev/null; then
        log_error "kustomize is not installed"
        exit 1
    fi
    
    if ! command -v argocd &> /dev/null; then
        log_warning "argocd CLI is not installed (optional)"
    fi
    
    log_success "Dependencies check passed"
}

validate_environment() {
    case $ENVIRONMENT in
        dev|staging|prod)
            log_info "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: dev, staging, prod"
            exit 1
            ;;
    esac
}

create_namespace() {
    local namespace=""
    case $ENVIRONMENT in
        dev)
            namespace="monitoring-dev"
            ;;
        staging)
            namespace="monitoring-staging"
            ;;
        prod)
            namespace="monitoring"
            ;;
    esac
    
    log_info "Creating namespace: $namespace"
    kubectl create namespace $namespace --dry-run=client -o yaml | kubectl apply -f -
    log_success "Namespace $namespace ready"
}

deploy_with_kustomize() {
    local overlay_path="$KUSTOMIZE_DIR/overlays/$ENVIRONMENT"
    
    if [ ! -d "$overlay_path" ]; then
        log_error "Overlay directory not found: $overlay_path"
        exit 1
    fi
    
    log_info "Deploying with Kustomize from $overlay_path"
    
    # Dry run first
    log_info "Performing dry run..."
    kustomize build "$overlay_path" | kubectl apply --dry-run=client -f -
    
    if [ $? -eq 0 ]; then
        log_success "Dry run passed"
        
        # Ask for confirmation for production
        if [ "$ENVIRONMENT" = "prod" ]; then
            read -p "Are you sure you want to deploy to PRODUCTION? (yes/no): " confirm
            if [ "$confirm" != "yes" ]; then
                log_info "Deployment cancelled"
                exit 0
            fi
        fi
        
        # Apply the manifests
        log_info "Applying manifests..."
        kustomize build "$overlay_path" | kubectl apply -f -
        log_success "Deployment completed"
    else
        log_error "Dry run failed"
        exit 1
    fi
}

deploy_with_argocd() {
    local app_file="$ARGOCD_APPS_DIR/lb-exporter-$ENVIRONMENT.yaml"
    
    if [ ! -f "$app_file" ]; then
        log_error "ArgoCD application file not found: $app_file"
        exit 1
    fi
    
    log_info "Deploying ArgoCD application from $app_file"
    
    # Apply the ArgoCD application
    kubectl apply -f "$app_file"
    log_success "ArgoCD application deployed"
    
    # Wait for sync if argocd CLI is available
    if command -v argocd &> /dev/null; then
        log_info "Waiting for ArgoCD sync..."
        argocd app sync "lb-exporter-$ENVIRONMENT" --timeout 300
        argocd app wait "lb-exporter-$ENVIRONMENT" --timeout 300
        log_success "ArgoCD sync completed"
    else
        log_info "ArgoCD CLI not available, check sync status manually"
    fi
}

check_deployment() {
    local namespace=""
    case $ENVIRONMENT in
        dev)
            namespace="monitoring-dev"
            ;;
        staging)
            namespace="monitoring-staging"
            ;;
        prod)
            namespace="monitoring"
            ;;
    esac
    
    log_info "Checking deployment status in namespace: $namespace"
    
    # Check deployment status
    kubectl get deployments -n $namespace
    
    # Check pod status
    kubectl get pods -n $namespace
    
    # Check service status
    kubectl get services -n $namespace
    
    # Wait for deployment to be ready
    local deployment_name=""
    case $ENVIRONMENT in
        dev)
            deployment_name="dev-lb-exporter"
            ;;
        staging)
            deployment_name="staging-lb-exporter"
            ;;
        prod)
            deployment_name="lb-exporter"
            ;;
    esac
    
    log_info "Waiting for deployment $deployment_name to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/$deployment_name -n $namespace
    
    if [ $? -eq 0 ]; then
        log_success "Deployment $deployment_name is ready"
    else
        log_error "Deployment $deployment_name failed to become ready"
        exit 1
    fi
}

cleanup() {
    local namespace=""
    case $ENVIRONMENT in
        dev)
            namespace="monitoring-dev"
            ;;
        staging)
            namespace="monitoring-staging"
            ;;
        prod)
            namespace="monitoring"
            ;;
    esac
    
    log_warning "Cleaning up resources in namespace: $namespace"
    
    if [ "$ENVIRONMENT" = "prod" ]; then
        read -p "Are you sure you want to cleanup PRODUCTION? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log_info "Cleanup cancelled"
            exit 0
        fi
    fi
    
    kubectl delete -k "$KUSTOMIZE_DIR/overlays/$ENVIRONMENT" || true
    log_success "Cleanup completed"
}

show_help() {
    cat << EOF
KT Cloud LB Exporter Deployment Script

Usage: $0 [ENVIRONMENT] [ACTION]

ENVIRONMENT:
    dev         Deploy to development environment
    staging     Deploy to staging environment
    prod        Deploy to production environment

ACTION:
    deploy      Deploy with Kustomize (default)
    argocd      Deploy with ArgoCD
    check       Check deployment status
    cleanup     Remove deployment
    help        Show this help message

Examples:
    $0 dev deploy       # Deploy to dev with Kustomize
    $0 staging argocd   # Deploy to staging with ArgoCD
    $0 prod check       # Check production deployment status
    $0 dev cleanup      # Remove dev deployment

EOF
}

# Main execution
main() {
    case $ACTION in
        deploy)
            check_dependencies
            validate_environment
            create_namespace
            deploy_with_kustomize
            check_deployment
            ;;
        argocd)
            check_dependencies
            validate_environment
            deploy_with_argocd
            ;;
        check)
            validate_environment
            check_deployment
            ;;
        cleanup)
            validate_environment
            cleanup
            ;;
        help)
            show_help
            ;;
        *)
            log_error "Invalid action: $ACTION"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"