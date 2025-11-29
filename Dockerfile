# Context Foundry Dashboard (Web UI only)
# The daemon runs on the host - this just serves the monitoring UI
FROM nginx:alpine

# Copy dashboard HTML
COPY tools/evolution/cf.html /usr/share/nginx/html/index.html
COPY tools/evolution/cf.html /usr/share/nginx/html/cf.html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose dashboard port
EXPOSE 8421

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost:8421/ || exit 1
