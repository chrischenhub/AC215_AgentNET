FROM node:20-alpine

ENV PORT=8080 \
    API_BASE_URL=/api

WORKDIR /usr/share/agentnet-frontend

RUN npm install -g http-server \
 && addgroup -S agentnet \
 && adduser -S agentnet -G agentnet

COPY . .

RUN chmod +x docker-entrypoint.sh \
 && chown -R agentnet:agentnet /usr/share/agentnet-frontend

USER agentnet

EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]
