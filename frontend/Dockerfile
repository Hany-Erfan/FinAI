FROM node:18-alpine

WORKDIR /app

COPY package*.json ./

# Install dependencies inside the container (Linux environment)
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]