 #!/bin/bash
 IMAGE_REF=$1
 DASHBOARD_PASSWORD=$2

 SECRETS_PATH="$HOME/.researchviewer-secrets"
 MONITORING_PATH="$HOME/dev/ResearchViewer/monitoring"

 echo "🔧 Setting up deployment directories..."

 # Ensure monitoring directory exists with proper permissions
 if [ ! -d "$MONITORING_PATH" ]; then
   echo "   Creating monitoring directory: $MONITORING_PATH"
   mkdir -p "$MONITORING_PATH"
 fi
 chmod 755 "$MONITORING_PATH"
 echo "   ✅ Monitoring directory ready"

 echo "🐳 Pulling Docker image: $IMAGE_REF"
 docker pull "$IMAGE_REF"

 echo "🛑 Stopping existing container..."
 docker stop researchviewer || true
 docker rm researchviewer || true

 echo "🚀 Starting new container..."
 docker run -d \
   --name researchviewer \
   --restart unless-stopped \
   -p 80:8080 \
   -v /home/shay/dev/ResearchViewer/src:/app/host_data \
   -v "$MONITORING_PATH:/app/monitoring" \
   -v "$SECRETS_PATH/firebase-service-account.json:/app/firebase-service-account.json:ro" \
   -e DATA_DB_PATH=/app/host_data/data.db \
   -e USER_DB_PATH=/app/host_data/user.db \
   -e FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json \
   -e DASHBOARD_PASSWORD="$DASHBOARD_PASSWORD" \
   "$IMAGE_REF"

 echo ""
 echo "⏳ Waiting for container to start..."
 sleep 3

 if docker ps | grep -q researchviewer; then
   echo "✅ Deployment successful!"
   echo ""
   echo "Container Status:"
   docker ps --filter name=researchviewer --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   echo ""
   echo "📊 Monitoring directory: $MONITORING_PATH"
   echo "🔍 Check logs with: docker logs researchviewer"
 else
   echo "❌ Container failed to start!"
   echo "Check logs with: docker logs researchviewer"
   exit 1
 fi