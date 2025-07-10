# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a KT Cloud Load Balancer monitoring solution built with Python and Kubernetes, consisting of:

1. **lb-exporter** - A Prometheus exporter that monitors KT Cloud Load Balancers
2. **Kubernetes manifests** - Deployment configuration for running the exporter in Kubernetes
3. **KT Cloud SDK** - Python libraries for interacting with KT Cloud APIs

## Architecture

### Core Components

**lb-exporter (`my-k8s-project/lb-exporter/`)**
- `lb-exporter.py` - Main Prometheus exporter application using atomic update pattern
- `kcldx.py` - KT Cloud DX zone SDK for API interactions
- `kclinstance.py` - KT Cloud instance management utilities
- `kclutil.py` - Common utilities for KT Cloud operations
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container image definition

**Kubernetes Manifests (`kubernetes-manifests/`)**
- `01-lb-exporter-secret.yaml` - Kubernetes secret for KT Cloud credentials
- `02-lb-exporter-deployment.yaml` - Deployment configuration
- `03-lb-exporter-service.yaml` - Service definition
- `04-grafana-ingress.yaml` - Grafana ingress configuration
- `05-prometheus-ingress.yaml` - Prometheus ingress configuration
- `prometheus-values.yaml` - Prometheus Helm chart values with lb-exporter scrape config
- `semascrd/` - Additional account configurations

### Application Architecture

**lb-exporter.py Features:**
- Atomic metric updates to prevent Prometheus scrape conflicts
- Thread-safe operations using RLock
- Comprehensive Load Balancer monitoring (status, servers, performance metrics)
- Error handling and retry logic
- Configurable scrape intervals (default: 60s)
- Exports on port 9105

**Key Metrics Exported:**
- `ktcloud_lb_total_count` - Total number of load balancers
- `ktcloud_lb_info` - Load balancer information and status
- `ktcloud_lb_server_count` - Number of servers per LB
- `ktcloud_lb_server_state` - Individual server states
- `ktcloud_server_current_connections` - Current connections per server
- `ktcloud_server_throughput_rate_kbps` - Server throughput rates
- `ktcloud_server_avg_ttfb_ms` - Average Time To First Byte
- `ktcloud_server_requests_rate_per_sec` - Requests per second per server

## Development Commands

### Docker Operations
```bash
# Build lb-exporter image
cd my-k8s-project/lb-exporter
docker build -t lb-exporter:latest .

# Run locally with environment variables
docker run -d \
  -e CLOUD_ID=your_cloud_id \
  -e CLOUD_PASSWORD=your_password \
  -e CLOUD_ZONE=DX-M1 \
  -p 9105:9105 \
  lb-exporter:latest
```

### Kubernetes Deployment
```bash
# Apply all manifests
kubectl apply -f kubernetes-manifests/

# Check deployment status
kubectl get pods -n monitoring
kubectl logs -n monitoring deployment/lb-exporter

# Port forward for local testing
kubectl port-forward -n monitoring svc/lb-exporter 9105:9105
```

### Helm Operations
```bash
# Install Helm (if needed)
./get_helm.sh

# Deploy Prometheus with lb-exporter configuration
helm install prometheus prometheus-community/kube-prometheus-stack \
  -f kubernetes-manifests/prometheus-values.yaml \
  -n monitoring --create-namespace
```

### Local Development
```bash
# Install Python dependencies
cd my-k8s-project/lb-exporter
pip install -r requirements.txt

# Set environment variables
export CLOUD_ID=your_cloud_id
export CLOUD_PASSWORD=your_password
export CLOUD_ZONE=DX-M1

# Run exporter locally
python lb-exporter.py
```

### Testing and Monitoring
```bash
# Check metrics endpoint
curl http://localhost:9105/metrics

# Test specific KT Cloud zones
# Supported zones: DX-M1, DX-Central, DX-DCN-CJ, DX-G, DX-G-YS
export CLOUD_ZONE=DX-Central

# Monitor logs
kubectl logs -n monitoring -f deployment/lb-exporter
```

## Configuration

### Required Environment Variables
- `CLOUD_ID` - KT Cloud account ID
- `CLOUD_PASSWORD` - KT Cloud account password  
- `CLOUD_ZONE` - KT Cloud zone (DX-M1, DX-Central, DX-DCN-CJ, DX-G, DX-G-YS)

### Key Configuration Files
- `prometheus-values.yaml` - Prometheus scrape configuration for lb-exporter
- `02-lb-exporter-deployment.yaml` - Kubernetes deployment with resource limits
- `01-lb-exporter-secret.yaml` - Encrypted storage for KT Cloud credentials

### Monitoring Configuration
- Default scrape interval: 60 seconds
- Metrics port: 9105
- Prometheus job name: `ktcloud-lb`
- Namespace: `monitoring`

## CI/CD Pipeline

### GitHub Actions (CI)
The project uses GitHub Actions for Continuous Integration with the following workflows:

**Main CI Pipeline (`.github/workflows/ci-pipeline.yml`)**
- Triggers on push to `main`/`develop` branches and PRs
- Code quality checks (linting, formatting, security scanning)
- Docker image build and push to KT Cloud registry
- Automated deployment to dev/staging environments
- GitOps repository updates for ArgoCD

**Security Scanning (`.github/workflows/security-scan.yml`)**
- Daily security scans of dependencies and container images
- Code security analysis with Bandit and Semgrep
- Kubernetes manifest security scanning
- Results uploaded to GitHub Security tab

**Required GitHub Secrets:**
- `REGISTRY_USERNAME` - KT Cloud registry username
- `REGISTRY_PASSWORD` - KT Cloud registry password
- `GITOPS_REPO` - GitOps repository URL
- `GITOPS_TOKEN` - GitHub token for GitOps repo access

### ArgoCD (CD)
GitOps-based continuous deployment using ArgoCD:

**Environment Structure:**
- `monitoring-dev` - Development environment (auto-sync enabled)
- `monitoring-staging` - Staging environment (auto-sync enabled)
- `monitoring` - Production environment (manual sync required)

**GitOps Repository Structure:**
```
k8s-manifests/
├── base/                    # Base Kustomize manifests
├── overlays/
│   ├── dev/                # Development overlay
│   ├── staging/            # Staging overlay
│   └── prod/               # Production overlay
└── argocd-apps/            # ArgoCD application definitions
```

### Deployment Commands

**Using Deployment Scripts:**
```bash
# Deploy to development
./scripts/deploy.sh dev deploy

# Deploy to staging with ArgoCD
./scripts/deploy.sh staging argocd

# Check production deployment status
./scripts/deploy.sh prod check

# Setup ArgoCD
./scripts/setup-argocd.sh install
```

**Manual Kustomize Deployment:**
```bash
# Deploy to development
kubectl apply -k k8s-manifests/overlays/dev

# Deploy to staging
kubectl apply -k k8s-manifests/overlays/staging

# Deploy to production
kubectl apply -k k8s-manifests/overlays/prod
```

**ArgoCD Application Management:**
```bash
# Install ArgoCD
./scripts/setup-argocd.sh install

# Check ArgoCD status
./scripts/setup-argocd.sh status

# Get admin password
./scripts/setup-argocd.sh password

# Access ArgoCD UI
./scripts/setup-argocd.sh port-forward
# Then open https://localhost:8080
```

### Environment-Specific Configuration

**Development Environment:**
- Namespace: `monitoring-dev`
- Replica count: 1
- Resource limits: 50m CPU, 64Mi memory
- Auto-sync enabled
- Image tag: `develop-latest`

**Staging Environment:**
- Namespace: `monitoring-staging`
- Replica count: 1
- Resource limits: 100m CPU, 128Mi memory
- Auto-sync enabled
- Image tag: `main-latest`

**Production Environment:**
- Namespace: `monitoring`
- Replica count: 2
- Resource limits: 200m CPU, 256Mi memory
- Manual sync required
- Image tag: specific version tags (e.g., `v1.0.0`)

## Important Notes

### Security Considerations
- Never commit KT Cloud credentials to version control
- Use Kubernetes secrets for credential management
- Rotate credentials regularly
- Monitor for unauthorized access attempts
- All container images are scanned for vulnerabilities
- RBAC and security contexts are enforced

### Performance Characteristics
- Atomic updates prevent data inconsistency during Prometheus scrapes
- Thread-safe operations using RLock
- Configurable collection intervals to balance freshness vs. API load
- Graceful error handling for individual LB failures

### KT Cloud API Integration
- Uses official KT Cloud DX SDK (`kcldx.py`)
- Supports multiple zones with zone-specific configurations
- Handles API rate limiting and connection failures
- Provides detailed logging for troubleshooting

## Troubleshooting

### Common Issues
1. **Connection failures**: Check KT Cloud credentials and zone configuration
2. **Missing metrics**: Verify Prometheus scrape configuration in `prometheus-values.yaml`
3. **High memory usage**: Adjust collection intervals or implement metric filtering
4. **Authentication errors**: Rotate KT Cloud credentials and update secrets
5. **CI/CD failures**: Check GitHub Actions logs and ArgoCD sync status

### Debugging Commands
```bash
# Check exporter logs
kubectl logs -n monitoring deployment/lb-exporter --tail=100

# Verify metrics endpoint
kubectl exec -n monitoring deployment/lb-exporter -- curl localhost:9105/metrics

# Test KT Cloud connectivity
kubectl exec -n monitoring deployment/lb-exporter -- python -c "import kcldx; print('SDK loaded')"

# Check ArgoCD application status
kubectl get applications -n argocd
argocd app get lb-exporter-prod

# View CI/CD pipeline logs
# Check GitHub Actions tab in repository
# Check ArgoCD UI at https://localhost:8080
```