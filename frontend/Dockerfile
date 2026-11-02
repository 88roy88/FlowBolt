ARG FRONTEND_BASE_IMAGE=node:24-slim
ARG NGINX_IMAGE=nginx:alpine

FROM ${FRONTEND_BASE_IMAGE} AS build

ARG NPM_REGISTRY=https://registry.npmjs.org/
ARG NPM_STRICT_SSL=true
RUN npm set registry ${NPM_REGISTRY}
RUN npm config set strict-ssl ${NPM_STRICT_SSL}

RUN npm install -g pnpm

WORKDIR /app

COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

USER root

COPY . .

ARG VITE_AUTH_PROVIDER_URL
ARG VITE_AUTH_STORAGE_KEY=Auth
ARG VITE_AUTH_USE_IFRAME=true
ARG VITE_AUTH_COOKIE_NAME
ARG VITE_AUTH_POST_MESSAGE_TARGET
ARG VITE_AUTH_POLL_INTERVAL_MS
ARG VITE_AUTH_POPUP_TIMEOUT_MS

ENV VITE_AUTH_PROVIDER_URL=$VITE_AUTH_PROVIDER_URL
ENV VITE_AUTH_STORAGE_KEY=$VITE_AUTH_STORAGE_KEY
ENV VITE_AUTH_USE_IFRAME=$VITE_AUTH_USE_IFRAME
ENV VITE_AUTH_COOKIE_NAME=$VITE_AUTH_COOKIE_NAME
ENV VITE_AUTH_POST_MESSAGE_TARGET=$VITE_AUTH_POST_MESSAGE_TARGET
ENV VITE_AUTH_POLL_INTERVAL_MS=$VITE_AUTH_POLL_INTERVAL_MS
ENV VITE_AUTH_POPUP_TIMEOUT_MS=$VITE_AUTH_POPUP_TIMEOUT_MS

RUN pnpm build

FROM ${NGINX_IMAGE}

RUN rm -f /etc/nginx/conf.d/default.conf

RUN chown -R nginx:nginx /var/cache/nginx /var/run && \
    chmod 777 /var/cache/nginx /var/run

COPY --chown=nginx:nginx nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=nginx:nginx --from=build /app/dist /usr/share/nginx/html

RUN sed -i 's/listen 80;/listen 8080;/' /etc/nginx/conf.d/default.conf

USER nginx

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
