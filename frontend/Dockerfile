FROM node:18-alpine

WORKDIR /app

COPY package*.json ./

# Install dependencies inside the container (Linux environment)
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]