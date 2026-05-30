FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

COPY server.py /app/
COPY client.py /app/
COPY test_demo.py /app/

RUN mkdir -p /var/www/chunks

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
