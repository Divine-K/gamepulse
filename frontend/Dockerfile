# syntax=docker/dockerfile:1
# --- build stage: compile the dashboard -----------------------------------------------------
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Empty = same origin: nginx proxies /api to the backend. Set an absolute URL to talk to an API
# hosted elsewhere (the API must then allow this origin in CORS_ORIGINS).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# --- runtime stage: static files behind nginx ------------------------------------------------
FROM nginx:1.29-alpine
ENV API_UPSTREAM=http://api:8000 \
    NGINX_ENVSUBST_FILTER=API_
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1
