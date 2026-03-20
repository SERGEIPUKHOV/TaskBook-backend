FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
ARG VITE_API_URL=http://localhost:8000/api/v1
ARG VITE_FRONTEND_URL=http://localhost:3001
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_FRONTEND_URL=${VITE_FRONTEND_URL}
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
