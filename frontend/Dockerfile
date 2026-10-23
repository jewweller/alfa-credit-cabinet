# Кабинет клиента и банка: сборка Vite → статика в nginx, /api проксируется в сервис api
# (план, раздел 9). Режим данных — VITE_API_MODE (mocks / mixed / real, src/mocks/mode.ts);
# пустой — по старому флагу VITE_USE_MOCKS (true — моки в браузере).

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_MODE=
ARG VITE_USE_MOCKS=true
ARG VITE_DEMO_MODE=true
ENV VITE_API_MODE=$VITE_API_MODE \
    VITE_USE_MOCKS=$VITE_USE_MOCKS \
    VITE_DEMO_MODE=$VITE_DEMO_MODE
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
