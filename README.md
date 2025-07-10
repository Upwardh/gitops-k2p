# KT Cloud Load Balancer Exporter

A Prometheus exporter for monitoring KT Cloud Load Balancers with enterprise-grade CI/CD pipeline.

## Quick Start

### Prerequisites
- Docker
- Kubernetes cluster
- KT Cloud account with API access
- GitHub account for CI/CD

### Local Development
```bash
# Clone the repository
git clone <repository-url>
cd ktcloud-api

# Install dependencies
cd my-k8s-project/lb-exporter
pip install -r requirements.txt

# Set environment variables
export CLOUD_ID=your_cloud_id
export CLOUD_PASSWORD=your_password  
export CLOUD_ZONE=DX-M1

# Run the exporter
python lb-exporter.py
```

### Quick Deployment
```bash
# Deploy to development
./scripts/deploy.sh dev deploy

# Setup ArgoCD for GitOps
./scripts/setup-argocd.sh install

# Deploy with ArgoCD
./scripts/deploy.sh staging argocd
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub        │    │   ArgoCD        │    │   Kubernetes    │
│   Actions       │───▶│   GitOps        │───▶│   Cluster       │
│   (CI)          │    │   (CD)          │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │   lb-exporter   │
                                              │   Pod           │
                                              └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │   KT Cloud      │
                                              │   Load          │
                                              │   Balancers     │
                                              └─────────────────┘
```

## Features

### Monitoring Capabilities
- **Real-time LB Monitoring**: Track load balancer status and performance
- **Server-level Metrics**: Individual backend server health and performance
- **Multi-zone Support**: Monitor across different KT Cloud zones
- **Prometheus Integration**: Native Prometheus metrics export

### CI/CD Pipeline
- **GitHub Actions**: Automated testing, building, and deployment
- **ArgoCD**: GitOps-based continuous deployment
- **Security Scanning**: Comprehensive vulnerability scanning
- **Multi-environment**: Development, staging, and production environments

### Security Features
- **Secret Management**: Kubernetes secrets for credential storage
- **RBAC**: Role-based access control
- **Security Scanning**: Container and dependency vulnerability scanning
- **Network Policies**: Secure pod-to-pod communication

## Supported KT Cloud Zones
- DX-M1
- DX-Central
- DX-DCN-CJ
- DX-G
- DX-G-YS

## Monitoring Metrics

The exporter provides 14 comprehensive metrics:

| Metric | Description |
|--------|-------------|
| `ktcloud_lb_total_count` | Total number of load balancers |
| `ktcloud_lb_info` | Load balancer information and status |
| `ktcloud_lb_server_count` | Number of servers per LB |
| `ktcloud_lb_server_state` | Individual server states |
| `ktcloud_server_current_connections` | Current connections per server |
| `ktcloud_server_throughput_rate_kbps` | Server throughput rates |
| `ktcloud_server_avg_ttfb_ms` | Average Time To First Byte |
| `ktcloud_server_requests_rate_per_sec` | Requests per second per server |

## CI/CD Workflow

### GitHub Actions Pipeline
1. **Code Quality**: Linting, formatting, security scanning
2. **Testing**: Unit tests and integration tests
3. **Build**: Docker image build and push
4. **Security**: Container vulnerability scanning
5. **Deploy**: Automated deployment to dev/staging

### ArgoCD GitOps
1. **Repository Sync**: Monitor GitOps repository for changes
2. **Application Sync**: Deploy changes to Kubernetes
3. **Health Checks**: Verify deployment health
4. **Rollback**: Automated rollback on failures

## Environment Configuration

### Development
- **Namespace**: `monitoring-dev`
- **Replicas**: 1
- **Resources**: 50m CPU, 64Mi memory
- **Auto-sync**: Enabled

### Staging
- **Namespace**: `monitoring-staging`
- **Replicas**: 1
- **Resources**: 100m CPU, 128Mi memory
- **Auto-sync**: Enabled

### Production
- **Namespace**: `monitoring`
- **Replicas**: 2
- **Resources**: 200m CPU, 256Mi memory
- **Auto-sync**: Manual approval required

## Getting Started

### 1. Setup GitHub Repository
```bash
# Fork this repository
# Add required secrets to GitHub:
# - REGISTRY_USERNAME
# - REGISTRY_PASSWORD
# - GITOPS_REPO
# - GITOPS_TOKEN
```

### 2. Configure Kubernetes Cluster
```bash
# Install ArgoCD
./scripts/setup-argocd.sh install

# Create namespaces
kubectl create namespace monitoring-dev
kubectl create namespace monitoring-staging
kubectl create namespace monitoring
```

### 3. Deploy Application
```bash
# Deploy to development
./scripts/deploy.sh dev deploy

# Deploy to staging
./scripts/deploy.sh staging argocd

# Deploy to production (manual approval required)
./scripts/deploy.sh prod argocd
```

### 4. Monitor Application
```bash
# Check deployment status
./scripts/deploy.sh prod check

# Access ArgoCD UI
./scripts/setup-argocd.sh port-forward
# Open https://localhost:8080

# Check metrics
kubectl port-forward -n monitoring svc/lb-exporter 9105:9105
curl http://localhost:9105/metrics
```

## Documentation

- [CLAUDE.md](CLAUDE.md) - Comprehensive development guide
- [CI/CD Pipeline](.github/workflows/) - GitHub Actions workflows
- [Kubernetes Manifests](k8s-manifests/) - Deployment configurations
- [ArgoCD Applications](k8s-manifests/argocd-apps/) - GitOps applications

## Security

- All container images are scanned for vulnerabilities
- Kubernetes security contexts are enforced
- RBAC is implemented for access control
- Secrets are encrypted at rest
- Network policies restrict pod communication

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `./scripts/test.sh`
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Support

For questions and support:
- Create an issue in the GitHub repository
- Check the troubleshooting section in [CLAUDE.md](CLAUDE.md)
- Review ArgoCD application logs