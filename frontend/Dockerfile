FROM node:20-alpine

WORKDIR /app

# Copy package files first for caching
COPY package.json package-lock.json* ./

RUN npm ci --ignore-scripts 2>/dev/null || npm install

# Copy source code
COPY . .

EXPOSE 5173

CMD ["npx", "vite", "--host", "0.0.0.0"]
