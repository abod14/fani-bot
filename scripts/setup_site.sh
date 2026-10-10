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
ADMIN_PORT=$(grep -E '^ADMIN_PANEL_PORT=' .env 2>/dev/null | cut -d= -f2); ADMIN_PORT=${ADMIN_PORT:-5050}
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
    location /panel/ { proxy_pass http://127.0.0.1:$ADMIN_PORT/; proxy_set_header Host \$host; proxy_set_header X-Forwarded-For \$remote_addr; proxy_set_header X-Forwarded-Proto \$scheme; proxy_set_header X-Forwarded-Prefix /panel; }
    location = /panel { return 301 /panel/; }
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
# لوحة التحكم على رابط مقفل https://$DOMAIN/panel — نضيفها لإعداد nginx الحالي (اللي عدّله certbot) مرة وحدة
NGX=/etc/nginx/sites-available/fanniapp
if ! grep -q "location /panel/" "$NGX"; then
  cp "$NGX" /root/fanniapp.nginx.bak
  sed -i "/location \/wa\//a\    location /panel/ { proxy_pass http://127.0.0.1:$ADMIN_PORT/; proxy_set_header Host \$host; proxy_set_header X-Forwarded-For \$remote_addr; proxy_set_header X-Forwarded-Proto \$scheme; proxy_set_header X-Forwarded-Prefix /panel; }" "$NGX"
  sed -i "/location \/panel\//a\    location = /panel { return 301 /panel/; }" "$NGX"
  if nginx -t >/dev/null 2>&1; then systemctl reload nginx; else cp /root/fanniapp.nginx.bak "$NGX"; echo "⚠️ ما قدرنا نضيف /panel لإعداد nginx — رجّعنا الإعداد القديم"; fi
fi
if grep -q "location /panel/" "$NGX" && curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://$DOMAIN/panel/login" | grep -q "200"; then
  touch .panel_https_ok
  echo "🔒 لوحة التحكم الآن على: https://$DOMAIN/panel  (الرابط القديم يحوّلك لها تلقائيًا)"
else
  rm -f .panel_https_ok
  echo "⚠️ رابط اللوحة المقفل لم يعمل بعد — الرابط القديم يبقى شغّالًا كما هو"
fi
echo "✅ الموقع يعمل: https://$DOMAIN"
echo "   سياسة الخصوصية: https://$DOMAIN/privacy"
