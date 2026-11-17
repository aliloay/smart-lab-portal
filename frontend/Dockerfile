# --- build ---------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- serve ---------------------------------------------------------------
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY app_locations.conf security_headers.conf tls.conf.template /etc/nginx/
COPY 40-smartlab-tls.sh /docker-entrypoint.d/40-smartlab-tls.sh
RUN sed -i 's/$//' /docker-entrypoint.d/40-smartlab-tls.sh /etc/nginx/*.conf /etc/nginx/tls.conf.template     && chmod +x /docker-entrypoint.d/40-smartlab-tls.sh
# Version stamp (tools/deploy/build_images.ps1, deploy.py): which web-app build is serving, at /version.json
ARG BUILD_COMMIT=unstamped
ARG BUILD_TIME=
RUN printf '{"id":"%s%s","commit":"%s","built_at":"%s"}' "$BUILD_COMMIT" "${BUILD_TIME:+-$BUILD_TIME}" "$BUILD_COMMIT" "$BUILD_TIME" > /usr/share/nginx/html/version.json
EXPOSE 80 8080 443 8443
