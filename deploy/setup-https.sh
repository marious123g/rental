#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 && $# == 2 ]] || { echo 'Usage: sudo bash deploy/setup-https.sh rental.example.com email@example.com'; exit 1; }
domain="$1"
[[ "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ && "$domain" == *.* ]] || { echo 'Invalid domain'; exit 1; }
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx
cat > /etc/nginx/sites-available/rental <<EOF
server {
    listen 80;
    server_name $domain;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
ln -sfn /etc/nginx/sites-available/rental /etc/nginx/sites-enabled/rental
nginx -t
systemctl enable --now nginx
systemctl reload nginx
certbot --nginx -d "$domain" --email "$2" --agree-tos --non-interactive --redirect
