# Prima SRE Tech Challenge - Solution Documentation

## Project Overview

This project implements a reliable Python API server with Docker, Infrastructure as Code (IaC), and Kubernetes deployment, focusing on system reliability and robustness. The solution addresses all requirements specified in the Prima SRE Tech Challenge 2025.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Task 1: Python API Server](#task-1-python-api-server)
3. [Task 2: Dockerizing the Application](#task-2-dockerizing-the-application)
4. [Task 3: Infrastructure as Code (IaC)](#task-3-infrastructure-as-code-iac)
5. [Task 4: Kubernetes Deployment with Helm](#task-4-kubernetes-deployment-with-helm)
6. [End-to-End Deployment Guide](#end-to-end-deployment-guide)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Reliability Features](#reliability-features)

## Architecture Overview

The solution architecture consists of the following components:

- **Python Flask API Server**: A RESTful API with endpoints for user management
- **Docker Container**: Containerization of the Python application
- **LocalStack**: Provides mock AWS services (S3 and DynamoDB) for local development
- **Terraform**: Infrastructure as Code for provisioning AWS resources
- **Kubernetes/Minikube**: Container orchestration platform
- **Helm Charts**: Package manager for Kubernetes applications

![Architecture Diagram](architecture-diagram.png)

## Task 1: Python API Server

A Python Flask API server with the following endpoints:

- `GET /users`: Retrieves a list of all users from DynamoDB
- `POST /user`: Creates a new user with an optional avatar image upload to S3
- `GET /health`: Health check endpoint for Kubernetes probes

### Implementation Details

The API server uses Flask and is structured to handle requests, process data, and interact with AWS services.

```python
from flask import Flask, request, jsonify
import boto3
import os
import uuid

app = Flask(__name__)

# AWS Configuration
AWS_REGION = "us-east-1"
DYNAMODB_TABLE = "users"
S3_BUCKET = "prima-tech-challenge"

# Use LocalStack endpoint if running locally
LOCALSTACK_ENDPOINT = "http://172.17.0.2:4566"

# Set environment variables for dummy credentials (Required for LocalStack)
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

# Initialize AWS clients with LocalStack endpoint
dynamodb = boto3.client("dynamodb", region_name=AWS_REGION, endpoint_url=LOCALSTACK_ENDPOINT)
s3 = boto3.client("s3", region_name=AWS_REGION, endpoint_url=LOCALSTACK_ENDPOINT)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route("/users", methods=["GET"])
def get_users():
    response = dynamodb.scan(TableName=DYNAMODB_TABLE)
    users = [{"id": item["id"]["S"], "name": item["name"]["S"], "email": item["email"]["S"], "avatar_url": item.get("avatar_url", {}).get("S", "")}
             for item in response.get("Items", [])]
    return jsonify(users)

@app.route("/user", methods=["POST"])
def create_user():
    user_id = str(uuid.uuid4())  # Generate unique ID

    if request.content_type == "application/json":
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        name = data.get("name")
        email = data.get("email")
        avatar_url = ""  # Default empty avatar URL if no file is uploaded

    else:  # Handle multipart/form-data (File Upload)
        name = request.form.get("name")
        email = request.form.get("email")

        if "avatar" in request.files:
            file = request.files["avatar"]
            file_ext = file.filename.split(".")[-1]
            avatar_filename = f"{uuid.uuid4()}.{file_ext}"
            s3.upload_fileobj(file, S3_BUCKET, avatar_filename)
            avatar_url = f"http://localhost:4566/{S3_BUCKET}/{avatar_filename}"
        else:
            avatar_url = ""

    # Validate required fields
    if not name or not email:
        return jsonify({"error": "Missing 'name' or 'email'"}), 400

    # Save to DynamoDB
    try:
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={
                "id": {"S": user_id},
                "name": {"S": name},
                "email": {"S": email},
                "avatar_url": {"S": avatar_url}
            },
        )
        return jsonify({"message": "User created successfully", "id": user_id, "avatar_url": avatar_url}), 201

    except Exception as e:
        print("DynamoDB Error:", e)  # Log error
        return jsonify({"error": "Failed to save user", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

### Key Features

- **Unique ID Generation**: Uses UUID for unique user identifiers
- **Error Handling**: Comprehensive error handling for common failure scenarios
- **Content Type Detection**: Supports both JSON and multipart/form-data requests
- **Health Check Endpoint**: For Kubernetes liveness and readiness probes

### Dependencies

```
flask
boto3
flask-cors
```

## Task 2: Dockerizing the Application

The application is containerized using Docker for consistent deployment across environments.

### Dockerfile

```dockerfile
# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]
```

### Build and Run Commands

```bash
# Build Docker image
docker build -t sansugupta/prima-api:latest .

# Run container locally
docker run -p 5000:5000 sansugupta/prima-api:latest

# Push to Docker Hub (if needed)
docker push sansugupta/prima-api:latest
```

## Task 3: Infrastructure as Code (IaC)

Terraform is used to provision the required AWS resources in LocalStack.

### Terraform Configuration (main.tf)

```terraform
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    dynamodb = "http://172.17.0.2:4566"
    s3       = "http://172.17.0.2:4566"
  }

  default_tags {
    tags = {
      Environment = "local"
    }
  }
}

resource "aws_dynamodb_table" "users" {
  name         = "users"
  billing_mode = "PROVISIONED"
  read_capacity  = 1
  write_capacity = 1
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

resource "aws_s3_bucket" "avatars" {
  bucket = "prima-tech-challenge"
}
```

### Applying Infrastructure

```bash
# Initialize Terraform
cd terraform
terraform init

# Apply configuration
terraform apply -auto-approve

# Import existing resources (if needed)
terraform import aws_dynamodb_table.users users
terraform import aws_s3_bucket.avatars prima-tech-challenge
```

## Task 4: Kubernetes Deployment with Helm

The application is deployed to Kubernetes using Helm Charts for both the API server and LocalStack.

### Helm Chart Structure

```
prima-api/
├── Chart.yaml
├── charts/
├── templates/
│   ├── NOTES.txt
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── hpa.yaml
│   ├── ingress.yaml
│   ├── localstack.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   └── tests/
└── values.yaml
```

### Values.yaml

```yaml
replicaCount: 2

image:
  repository: sansugupta/prima-api
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 5000

resources:
  limits:
    cpu: "500m"
    memory: "512Mi"
  requests:
    cpu: "250m"
    memory: "256Mi"

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 50
  targetMemoryUtilizationPercentage: 80

env:
  AWS_REGION: "us-east-1"
  DYNAMODB_TABLE: "users"
  S3_BUCKET: "prima-tech-challenge"
  LOCALSTACK_URL: "http://localstack.default.svc.cluster.local:4566"

ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: prima-api.local
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls: []

serviceAccount:
  create: true
  name: "prima-api-sa"
```

### Deployment Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-api
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-api
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-api
    spec:
      containers:
      - name: api
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        env:
        - name: AWS_REGION
          value: "{{ .Values.env.AWS_REGION }}"
        - name: DYNAMODB_TABLE
          value: "{{ .Values.env.DYNAMODB_TABLE }}"
        - name: S3_BUCKET
          value: "{{ .Values.env.S3_BUCKET }}"
        - name: LOCALSTACK_URL
          value: "{{ .Values.env.LOCALSTACK_URL }}"
        - name: DYNAMODB_ENDPOINT
          value: "{{ .Values.env.LOCALSTACK_URL }}"
        ports:
        - containerPort: 5000
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ .Release.Name }}-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ .Release.Name }}-api
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
```

### Service Configuration

```yaml
apiVersion: v1
kind: Service
metadata:
  name: prima-api-service
spec:
  selector:
    app: prima-api-api
  ports:
    - protocol: TCP
      port: 5000
      targetPort: 5000
      nodePort: 30000
  type: NodePort
```

### LocalStack Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: localstack
spec:
  replicas: 1
  selector:
    matchLabels:
      app: localstack
  template:
    metadata:
      labels:
        app: localstack
    spec:
      containers:
        - name: localstack
          image: localstack/localstack
          ports:
            - containerPort: 4566
          env:
            - name: SERVICES
              value: "s3,dynamodb"
---
apiVersion: v1
kind: Service
metadata:
  name: localstack
spec:
  selector:
    app: localstack
  ports:
    - protocol: TCP
      port: 4566
      targetPort: 4566
```

### Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: prima-api-ingress
spec:
  rules:
  - host: prima-api.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: prima-api-service
            port:
              number: 5000
```

## End-to-End Deployment Guide

### Prerequisites

- Docker installed
- Minikube installed
- kubectl installed
- Terraform installed
- Helm installed

### Step 1: Start Minikube and Enable Ingress

```bash
# Start Minikube
minikube start

# Enable Ingress controller
minikube addons enable ingress
```

### Step 2: Deploy LocalStack

```bash
# Apply LocalStack deployment and service
kubectl apply -f localstack.yaml

# Verify LocalStack is running
kubectl get pods -l app=localstack
```

### Step 3: Provision AWS Resources with Terraform

```bash
# Navigate to terraform directory
cd terraform

# Initialize Terraform
terraform init

# Apply Terraform configuration
terraform apply -auto-approve
```

### Step 4: Build and Push Docker Image

```bash
# Build Docker image
docker build -t sansugupta/prima-api:latest .

# Push to Docker Hub (if needed)
docker push sansugupta/prima-api:latest
```

### Step 5: Deploy API with Helm

```bash
# Install Helm chart
helm install prima-api ./prima-api

# Verify deployment
kubectl get pods -l app=prima-api-api
```

### Step 6: Verify External Access

```bash
# Get Minikube IP
minikube ip

# Add host entry for ingress (if using ingress)
echo "$(minikube ip) prima-api.local" | sudo tee -a /etc/hosts

# Test API (with NodePort)
curl http://$(minikube ip):30000/health

# Test API (with Ingress)
curl http://prima-api.local/health
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Pods Crashing or Not Ready

**Issue:**
```
kubectl get pods
NAME                           READY   STATUS    RESTARTS      AGE
prima-api-api-564668fc54-bz2d5 0/1     Running   2 (44s ago)   5m6s
```

**Troubleshooting:**
```bash
# Check pod logs
kubectl logs prima-api-api-564668fc54-bz2d5

# Describe pod for events
kubectl describe pod prima-api-api-564668fc54-bz2d5
```

**Solutions:**
- Increase probe initialDelaySeconds if the application takes time to start
- Check environment variables and connection strings
- Verify that LocalStack is accessible from the API pods

#### 2. API Cannot Connect to LocalStack

**Issue:** API pods cannot reach LocalStack service.

**Solution:** Deploy LocalStack in the same Kubernetes cluster:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: localstack
spec:
  replicas: 1
  selector:
    matchLabels:
      app: localstack
  template:
    metadata:
      labels:
        app: localstack
    spec:
      containers:
        - name: localstack
          image: localstack/localstack
          env:
            - name: SERVICES
              value: "s3,dynamodb"
            - name: DEFAULT_REGION
              value: "us-east-1"
          ports:
            - containerPort: 4566
              name: http

---
apiVersion: v1
kind: Service
metadata:
  name: localstack
spec:
  selector:
    app: localstack
  ports:
    - protocol: TCP
      port: 4566
      targetPort: 4566
```

Update API configuration to use the Kubernetes service name:
```python
LOCALSTACK_ENDPOINT = "http://localstack.default.svc.cluster.local:4566"
```

#### 3. Service Not Accessible Externally

**Issue:** API service is not accessible from outside the cluster.

**Solution:** Change service type from ClusterIP to NodePort:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: prima-api-service
spec:
  selector:
    app: prima-api-api
  ports:
    - protocol: TCP
      port: 5000
      targetPort: 5000
      nodePort: 30000
  type: NodePort
```

#### 4. Terraform Resource Conflicts

**Issue:** Terraform reports conflicts with existing resources.

**Solution:** Import existing resources into Terraform state:

```bash
terraform import aws_dynamodb_table.users users
terraform import aws_s3_bucket.avatars prima-tech-challenge
```

## Reliability Features

This implementation includes several reliability features to ensure robust operation:

### Application Level

- **Health Check Endpoint**: `/health` endpoint for Kubernetes probes
- **Error Handling**: Comprehensive error handling for API requests
- **Input Validation**: Validation of required fields and input data
- **Exception Logging**: Logging of errors for troubleshooting

### Infrastructure Level

- **Horizontal Pod Autoscaling**: Automatic scaling based on CPU and memory usage
- **Resource Limits**: Defined CPU and memory limits for containers
- **Liveness and Readiness Probes**: Health monitoring for automatic recovery
- **Replicated Deployment**: Multiple replicas for high availability
- **Infrastructure as Code**: Reproducible infrastructure with Terraform

### Kubernetes Configuration

- **Graceful Termination**: Proper shutdown handling with termination grace period
- **Service Discovery**: Automatic service discovery within the cluster
- **External Access**: Multiple options for external access (NodePort, Ingress)
- **Helm Packaging**: Simplified deployment and upgrades with Helm

---

## Conclusion

This project demonstrates a comprehensive implementation of a reliable Python API server with Docker, Infrastructure as Code, and Kubernetes. The solution incorporates best practices for system reliability, containerization, and cloud-native application deployment.

For any questions or issues, please reach out to the project maintainers.
