# Kubernetes Deployment Guide

This skill covers deploying containerized applications to Kubernetes clusters,
including strategy selection, rollback procedures, and production hardening.

## Prerequisites

Ensure the following tools and access are configured before deployment.

### kubectl Setup

Install kubectl matching your cluster version:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
kubectl version --client
```

Verify connectivity with `kubectl cluster-info`.

### Cluster Access

Configure kubeconfig for your target cluster:

```bash
export KUBECONFIG=~/.kube/config
kubectl config use-context production
kubectl get nodes
```

For multi-cluster setups, use `kubectx` to switch contexts.

### Container Registry

Ensure your images are pushed to an accessible registry:

- Docker Hub: `docker push myorg/myapp:v1.2.3`
- ECR: `aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com`
- GCR: `gcloud auth configure-docker && docker push gcr.io/project/myapp:v1.2.3`

## Deployment Strategies

Choose the strategy that matches your risk tolerance and traffic requirements.

### Rolling Update

The default Kubernetes strategy. Gradually replaces old pods with new ones.

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

**When to use**: Standard deployments where brief mixed-version traffic is acceptable.

**Rollback**: `kubectl rollout undo deployment/myapp`

### Blue-Green Deployment

Run two identical environments. Switch traffic atomically.

1. Deploy new version as `myapp-green` alongside existing `myapp-blue`
2. Run smoke tests against green
3. Switch the Service selector to point to green
4. Drain and remove blue

**Traffic Switching**

Update the service selector to cut over:

```bash
kubectl patch svc myapp -p '{"spec":{"selector":{"version":"green"}}}'
```

**Rollback**: Patch selector back to `blue`. Instant, zero-downtime.

### Canary Deployment

Gradually shift traffic to the new version. Monitor metrics at each step.

1. Deploy canary with 1 replica
2. Route 5% traffic via Istio/Nginx weight
3. Monitor error rate and latency for 10 minutes
4. If healthy, scale to 25%, 50%, 100%
5. Remove old deployment

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
spec:
  http:
  - route:
    - destination:
        host: myapp
        subset: stable
      weight: 95
    - destination:
        host: myapp
        subset: canary
      weight: 5
```

**Key metrics to watch**: p99 latency, 5xx rate, pod restart count.

---

## Resource Management

Configure resource requests and limits to prevent noisy-neighbor issues.

### CPU and Memory

```yaml
resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

**Rules of thumb**:
- Requests = what the app needs under normal load
- Limits = maximum before OOMKill or throttle
- Start with 2x request as limit, tune from metrics

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Troubleshooting

Common failure modes and their diagnostic steps.

### Pod Failures

**CrashLoopBackOff**:
```bash
kubectl logs myapp-pod --previous
kubectl describe pod myapp-pod
```
Check: missing env vars, failed health probes, OOMKilled.

**ImagePullBackOff**:
- Verify image tag exists: `docker manifest inspect myorg/myapp:v1.2.3`
- Check imagePullSecrets are configured
- Verify registry credentials haven't expired

### Network Issues

**Service not reachable**:
```bash
kubectl get endpoints myapp-svc
kubectl run debug --image=busybox --rm -it -- wget -qO- http://myapp-svc:8080/health
```

**DNS resolution failures**:
```bash
kubectl run debug --image=busybox --rm -it -- nslookup myapp-svc.default.svc.cluster.local
```

Check CoreDNS pods: `kubectl get pods -n kube-system -l k8s-app=kube-dns`

### Performance Degradation

**High latency**:
1. Check HPA status: `kubectl get hpa`
2. Look for CPU throttling: `kubectl top pods`
3. Review resource limits — are pods being throttled?
4. Check node pressure: `kubectl describe node | grep -A5 Conditions`

**Memory leaks**:
- Monitor pod memory over time via Prometheus/Grafana
- Set memory limits to trigger OOMKill before node pressure
- Use `kubectl top pods --sort-by=memory` to find offenders
