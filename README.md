# KT Cloud Load Balancer Monitoring

GitOps-based monitoring solution for KT Cloud Load Balancers using Prometheus, Grafana, and ArgoCD.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub        │    │   ArgoCD        │    │   Kubernetes    │
│   Repository    │───▶│   GitOps        │───▶│   Cluster       │
│   (Source)      │    │   (CD)          │    │   (Target)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
         ▼                                              ▼
┌─────────────────┐                           ┌─────────────────┐
│   CI Pipeline   │                           │   Monitoring    │
│   (GitHub       │                           │   Stack         │
│   Actions)      │                           │   (3 Envs)      │
└─────────────────┘                           └─────────────────┘
```

## 📁 Repository Structure

```
├── .github/workflows/          # CI/CD Pipeline
│   └── ci-build.yml           # Docker build and GitOps update
├── src/lb-exporter/           # LB Exporter Source Code
│   ├── lb-exporter.py         # Main exporter application
│   ├── kcldx.py              # KT Cloud DX SDK
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile            # Container image
├── environments/              # Environment Configurations
│   ├── dev/                  # Development Environment
│   │   ├── lb-exporter/      # LB Exporter manifests
│   │   └── monitoring/       # Prometheus & Grafana config
│   ├── staging/              # Staging Environment
│   │   ├── lb-exporter/      # LB Exporter manifests
│   │   └── monitoring/       # Prometheus & Grafana config
│   └── prod/                 # Production Environment
│       ├── lb-exporter/      # LB Exporter manifests
│       └── monitoring/       # Prometheus & Grafana config
└── argocd/                   # ArgoCD Applications
    ├── project.yaml          # ArgoCD project definition
    └── applications/         # Application definitions
        ├── lb-exporter-dev.yaml
        ├── lb-exporter-staging.yaml
        └── lb-exporter-prod.yaml
```

## 🚀 Quick Start

### Prerequisites
- Kubernetes cluster with ArgoCD installed
- GitHub repository with CI/CD secrets configured
- KT Cloud account with API access

### Deploy ArgoCD Applications
```bash
# Apply ArgoCD project and applications
kubectl apply -f argocd/project.yaml
kubectl apply -f argocd/applications/

# Check application status
kubectl get applications -n argocd
```

### Environment Access
- **Development**: [dev.grafana.devtron.click](http://dev.grafana.devtron.click)
- **Staging**: [staging.grafana.devtron.click](http://staging.grafana.devtron.click)
- **Production**: [prod.grafana.devtron.click](http://prod.grafana.devtron.click)

## 📊 Monitoring Dashboards

### Available Dashboards
1. **KT Cloud Test (DX-M1)** - `dashboard-ktcloud-test-dx-m1.json`
2. **Semascrd (DX-G-YS)** - `dashboard-semascrd-dx-g-ys.json`
3. **Account All (Combined)** - `dashboard-ktcloud-account-all.json`

### Key Metrics
- `ktcloud_lb_total_count` - Total load balancers
- `ktcloud_lb_info` - LB information and status
- `ktcloud_lb_server_count` - Servers per LB
- `ktcloud_lb_server_state` - Individual server states
- `ktcloud_server_current_connections` - Current connections
- `ktcloud_server_throughput_rate_kbps` - Throughput rates
- `ktcloud_server_avg_ttfb_ms` - Average response time
- `ktcloud_server_requests_rate_per_sec` - Requests per second

## 🔧 Configuration

### Environment Variables
```yaml
CLOUD_ID: "your_kt_cloud_id"
CLOUD_PASSWORD: "your_kt_cloud_password"
CLOUD_ZONE: "DX-M1"  # or DX-G-YS, DX-Central, etc.
```

### Supported KT Cloud Zones
- **DX-M1**: Primary monitoring zone
- **DX-G-YS**: Secondary monitoring zone
- **DX-Central, DX-DCN-CJ, DX-G**: Additional zones

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow
1. **Trigger**: Push to `main` branch or PR to `main`
2. **Build**: Docker image build and push to KT Cloud registry
3. **Update**: Automatic manifest updates via GitOps
4. **Deploy**: ArgoCD auto-sync to environments

### GitOps Flow
1. **Code Push** → GitHub Actions builds image
2. **Image Update** → Manifests updated automatically
3. **ArgoCD Sync** → Deployments updated in Kubernetes
4. **Health Check** → Verify deployment success

## 🌍 Environment Strategy

| Environment | Namespace | Replicas | Auto-Sync | Resources |
|-------------|-----------|----------|-----------|-----------|
| **Development** | `monitoring-dev` | 1 | ✅ Enabled | 50m CPU, 64Mi RAM |
| **Staging** | `monitoring-staging` | 1 | ✅ Enabled | 100m CPU, 128Mi RAM |
| **Production** | `monitoring` | 2 | ❌ Manual | 200m CPU, 256Mi RAM |

## 🛠️ Development

### Local Development
```bash
# Clone repository
git clone https://github.com/Upwardh/gitops-k2p.git
cd gitops-k2p

# Build lb-exporter
cd src/lb-exporter
docker build -t lb-exporter:local .

# Run locally
export CLOUD_ID=your_id
export CLOUD_PASSWORD=your_password
export CLOUD_ZONE=DX-M1
python lb-exporter.py
```

### Contributing
1. Fork the repository
2. Create feature branch from `main`
3. Make changes to `src/` or `environments/`
4. Push to trigger CI/CD pipeline
5. Create Pull Request

## 🔒 Security

- All credentials stored in Kubernetes secrets
- Container images scanned for vulnerabilities
- RBAC policies enforced
- Network policies restrict access
- GitOps ensures auditable deployments

## 📚 Documentation

- **Architecture**: GitOps-based with environment isolation
- **Monitoring**: Prometheus metrics + Grafana dashboards
- **Deployment**: ArgoCD applications with automatic sync
- **CI/CD**: GitHub Actions for build and deployment

## 🆘 Troubleshooting

### Common Issues
1. **ArgoCD sync failures**: Check namespace and RBAC permissions
2. **No metrics data**: Verify KT Cloud credentials and connectivity
3. **Dashboard not loading**: Check Grafana pod status and ingress

### Debug Commands
```bash
# Check ArgoCD applications
kubectl get applications -n argocd

# Check lb-exporter logs
kubectl logs -n monitoring-dev deployment/dev-lb-exporter

# Test metrics endpoint
kubectl port-forward -n monitoring-dev svc/dev-lb-exporter 9105:9105
curl http://localhost:9105/metrics

# Check Grafana access
kubectl get ingress -A
```

---

**Generated with GitOps best practices** 🚀