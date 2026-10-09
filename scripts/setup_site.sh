#!/usr/bin/env bash
# موقع «فنّي» على fanniapp.com (نفس السيرفر): nginx + شهادة https مجانية (Let's Encrypt).
# كمان يمرّر /wa/ و /privacy لخادم واتساب — رابط ثابت للـ Webhook بدل رابط trycloudflare المؤقت.
#   cd /root/fani-bot && bash scripts/setup_site.sh
# يُعاد تشغيله بأمان لتحديث الصفحة أو لإكمال https بعد ما يشتغل الـ DNS.
set -e
DOMAIN=fanniapp.com
cd "$(dirname "$0")/.."
if ! command -v nginx >/dev/null 2>&1 || ! command -v certbot >/dev/null 2>&1; then
  echo "⏳ تثبيت nginx و certbot..."
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx certbot python3-certbot-nginx >/dev/null
fi
mkdir -p /var/www/fanniapp && cp -r site/* /var/www/fanniapp/
WA_PORT=$(grep -E '^WA_PORT=' .env 2>/dev/null | cut -d= -f2); WA_PORT=${WA_PORT:-5070}
if [ ! -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]; then
cat > /etc/nginx/sites-available/fanniapp <<NGX
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;
    root /var/www/fanniapp;
    index index.html;
    location /wa/ { proxy_pass http://127.0.0.1:$WA_PORT; proxy_set_header Host \$host; proxy_set_header X-Forwarded-For \$remote_addr; }
    location = /privacy { proxy_pass http://127.0.0.1:$WA_PORT; }
    location / { try_files \$uri \$uri/ =404; }
}
NGX
fi
ln -sf /etc/nginx/sites-available/fanniapp /etc/nginx/sites-enabled/fanniapp
rm -f /etc/nginx/sites-enabled/default
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then ufw allow 'Nginx Full' >/dev/null; fi
nginx -t >/dev/null 2>&1 && systemctl enable nginx >/dev/null 2>&1 && systemctl reload nginx || systemctl restart nginx
MYIP=$(curl -s4 --max-time 10 ifconfig.me || true)
DNSIP=$(getent ahostsv4 $DOMAIN | awk 'NR==1{print $1}')
if [ "$DNSIP" != "$MYIP" ]; then
  echo "⏳ الصفحة جاهزة على السيرفر، لكن النطاق $DOMAIN ما يشير للسيرفر بعد ($DNSIP ≠ $MYIP)."
  echo "   أضف سجل A في GoDaddy ثم انتظر قليلًا وأعد تشغيل نفس الأمر لتفعيل https."
  exit 0
fi
if [ ! -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]; then
  WWW=""; [ "$(getent ahostsv4 www.$DOMAIN | awk 'NR==1{print $1}')" = "$MYIP" ] && WWW="-d www.$DOMAIN"
  certbot --nginx -d $DOMAIN $WWW --non-interactive --agree-tos --register-unsafely-without-email --redirect >/dev/null
fi
echo "✅ الموقع يعمل: https://$DOMAIN"
echo "   سياسة الخصوصية: https://$DOMAIN/privacy"
