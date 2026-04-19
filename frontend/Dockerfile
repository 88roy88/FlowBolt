ARG BASE_IMAGE=node:20-slim
FROM ${BASE_IMAGE} AS build

COPY .npmrc* ./

RUN npm install -g pnpm

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

USER root

COPY . .
RUN pnpm build

ARG NGINX_IMAGE=nginx:alpine
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
