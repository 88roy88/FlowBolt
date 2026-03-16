FROM node:20-slim AS base
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

# Install dependencies
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

# Build
COPY . .
RUN pnpm build

# Production — serve via nginx
FROM nginx:alpine
COPY --from=base /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
