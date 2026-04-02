 #!/bin/bash
 IMAGE_REF=$1

 SECRETS_PATH="$HOME/.researchviewer-secrets"

 docker pull "$IMAGE_REF"
 docker stop researchviewer || true
 docker rm researchviewer || true
 docker run -d \
   --name researchviewer \
   --restart unless-stopped \
   -p 80:8080 \
   -v /home/shay/dev/ResearchViewer/src:/app/host_data \
   -v /home/shay/dev/ResearchViewer/monitoring:/app/monitoring \
   -v "$SECRETS_PATH/firebase-service-account.json:/app/firebase-service-account.json:ro" \
   -e DATA_DB_PATH=/app/host_data/data.db \
   -e USER_DB_PATH=/app/host_data/user.db \
   -e FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json \
   "$IMAGE_REF"