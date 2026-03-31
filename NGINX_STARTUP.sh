#!/bin/bash
# Nginx容器启动脚本（带正确的volume挂载）

docker stop zhineng-nginx 2>/dev/null || true
docker rm zhineng-nginx 2>/dev/null || true

docker run -d --name zhineng-nginx \
  --network zhineng-knowledge-system_zhineng-network \
  -p 8008:80 \
  -v /home/ai/zhineng-knowledge-system/nginx/nginx.conf:/etc/nginx/nginx.conf:ro \
  -v /home/ai/zhineng-knowledge-system/frontend:/usr/share/nginx/html:ro \
  --restart unless-stopped \
  nginx:alpine

echo "✅ Nginx已启动，访问: http://100.66.1.8:8008"
