#!/usr/bin/env bash
# تجهيز بوت واتساب «فني» التجريبي على السيرفر — أمر واحد:
#   bash whatsapp_bot/setup.sh        ← أول مرة (يطلب Phone number ID والتوكن)
#   bash whatsapp_bot/setup.sh url    ← يعرض رابط الـ Webhook الحالي ورمز التحقق فقط
#   bash whatsapp_bot/setup.sh token  ← تحديث التوكن فقط (لو انتهى التوكن المؤقت)
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
ENV="$DIR/.env"
PORT=5070
touch "$ENV"

show_url() {
  local URL=""
  for i in $(seq 1 30); do
    URL=$(journalctl -u fani-tunnel -n 300 --no-pager 2>/dev/null | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
    [ -n "$URL" ] && break
    sleep 2
  done
  local VERIFY
  VERIFY=$(grep -E '^WA_VERIFY_TOKEN=' "$ENV" | cut -d= -f2-)
  echo
  echo "=============================================================="
  echo " انسخ هذين في ميتا: WhatsApp ← Configuration ← Webhook ← Edit"
  echo
  echo " Callback URL:  ${URL:-(ما ظهر بعد — شغّل: bash whatsapp_bot/setup.sh url)}/wa/webhook"
  echo " Verify token:  $VERIFY"
  echo
  echo " وبعدها في Webhook fields فعّل (Subscribe) خانة: messages"
  echo
  echo " رابط سياسة الخصوصية (لإعدادات التطبيق قبل النشر):"
  echo " ${URL:-...}/privacy"
  echo "=============================================================="
}

if [ "$1" = "url" ]; then show_url; exit 0; fi

if [ "$1" = "token" ]; then
  read -rsp "الصق Access Token الجديد (ما راح يظهر وأنت تلصقه) ثم Enter: " TOKEN; echo
  [ -z "$TOKEN" ] && { echo "❌ ما لصقت شي"; exit 1; }
  sed -i '/^WA_TOKEN=/d' "$ENV"; printf 'WA_TOKEN=%s\n' "$TOKEN" >> "$ENV"
  systemctl restart fani-wa && echo "✅ تم تحديث التوكن"
  exit 0
fi

echo "=== تجهيز بوت واتساب «فني» (تجريبي) ==="
read -rp "الصق Phone number ID (من صفحة API Setup) ثم Enter: " PNID
read -rsp "الصق Access Token (ما راح يظهر وأنت تلصقه) ثم Enter: " TOKEN; echo
PNID=$(echo "$PNID" | tr -cd '0-9')
if [ -z "$PNID" ] || [ -z "$TOKEN" ]; then echo "❌ لازم تلصق الاثنين"; exit 1; fi

VERIFY=$(grep -E '^WA_VERIFY_TOKEN=' "$ENV" | cut -d= -f2-)
[ -z "$VERIFY" ] && VERIFY="fanni$(head -c 32 /dev/urandom | sha256sum | cut -c1-12)"
sed -i '/^WA_TOKEN=/d;/^WA_PHONE_NUMBER_ID=/d;/^WA_VERIFY_TOKEN=/d;/^WA_PORT=/d' "$ENV"
printf 'WA_TOKEN=%s\nWA_PHONE_NUMBER_ID=%s\nWA_VERIFY_TOKEN=%s\nWA_PORT=%s\n' "$TOKEN" "$PNID" "$VERIFY" "$PORT" >> "$ENV"
chmod 600 "$ENV"

# نفس بايثون بوت تلغرام (فيه كل المكتبات المطلوبة)
PY=$(systemctl show -p ExecStart fani-bot 2>/dev/null | grep -o 'path=[^ ;]*' | head -1 | cut -d= -f2)
[ -x "$PY" ] || PY=$(command -v python3)

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "⏳ تنزيل cloudflared (رابط https مجاني للتجربة)..."
  curl -fsSL -o /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x /usr/local/bin/cloudflared
fi

cat > /etc/systemd/system/fani-wa.service <<EOF
[Unit]
Description=Fanni WhatsApp bot (trial)
After=network.target

[Service]
WorkingDirectory=$DIR
ExecStart=$PY $DIR/whatsapp_bot/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/fani-tunnel.service <<EOF
[Unit]
Description=Fanni WhatsApp tunnel (trycloudflare, trial)
After=network-online.target fani-wa.service

[Service]
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:$PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fani-wa fani-tunnel >/dev/null 2>&1
systemctl restart fani-wa fani-tunnel
echo "⏳ لحظات..."
sleep 6
if curl -fs "http://127.0.0.1:$PORT/wa/health" >/dev/null; then
  echo "✅ بوت واتساب شغال"
else
  echo "⚠️ البوت ما اشتغل — أرسل لي ناتج هذا الأمر: journalctl -u fani-wa -n 30 --no-pager"
fi
show_url
