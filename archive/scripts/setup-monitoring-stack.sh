#!/bin/bash

# 환경별 Prometheus + Grafana 스택 설치 스크립트
# 사용법: ./setup-monitoring-stack.sh <environment> <grafana-domain>
# 예시: ./setup-monitoring-stack.sh dev grafana-dev.devtron.click

set -e

ENVIRONMENT=${1}
GRAFANA_DOMAIN=${2}

if [[ -z "$ENVIRONMENT" || -z "$GRAFANA_DOMAIN" ]]; then
    echo "사용법: $0 <environment> <grafana-domain>"
    echo "예시: $0 dev grafana-dev.devtron.click"
    exit 1
fi

NAMESPACE="monitoring-${ENVIRONMENT}"

echo "🚀 ${ENVIRONMENT} 환경에 모니터링 스택 설치 중..."
echo "📍 네임스페이스: ${NAMESPACE}"
echo "🌐 Grafana 도메인: ${GRAFANA_DOMAIN}"

# 네임스페이스 생성
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# Prometheus Helm 리포지토리 추가
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 환경별 Prometheus + Grafana 스택 설치
cat <<EOF | helm upgrade --install prometheus-${ENVIRONMENT} prometheus-community/kube-prometheus-stack \
  --namespace ${NAMESPACE} \
  --values -
global:
  rbac:
    create: true

prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false
    retention: 7d
    scrapeInterval: 30s
    evaluationInterval: 30s
    
grafana:
  enabled: true
  adminPassword: admin123!
  persistence:
    enabled: true
    size: 1Gi
  ingress:
    enabled: true
    ingressClassName: nginx
    hosts:
      - ${GRAFANA_DOMAIN}
    annotations:
      kubernetes.io/ingress.class: nginx
      
  datasources:
    datasources.yaml:
      apiVersion: 1
      datasources:
      - name: Prometheus
        type: prometheus
        url: http://prometheus-${ENVIRONMENT}-kube-prometheus-prometheus:9090
        access: proxy
        isDefault: true

alertmanager:
  enabled: true

nodeExporter:
  enabled: true

kubeStateMetrics:
  enabled: true

prometheusOperator:
  enabled: true
EOF

echo "✅ ${ENVIRONMENT} 환경 모니터링 스택 설치 완료!"
echo "🌐 Grafana 접속: http://${GRAFANA_DOMAIN}"
echo "🔐 기본 로그인: admin / admin123!"
echo ""
echo "📊 대시보드 가져오기:"
echo "   - KT Cloud LB Dashboard ID: (사용자 제공 필요)"
echo "   - Node Exporter: 1860"
echo "   - Kubernetes Cluster: 7249"