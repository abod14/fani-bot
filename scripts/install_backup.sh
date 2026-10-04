#!/usr/bin/env bash
# يفعّل النسخة الاحتياطية اليومية (الساعة 3 الفجر بتوقيت السيرفر) ويسوي أول نسخة الحين.
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
PY=$(systemctl show -p ExecStart fani-bot 2>/dev/null | grep -o 'path=[^ ;]*' | head -1 | cut -d= -f2)
[ -x "$PY" ] || PY=$(command -v python3)
FIRST_TIME=1
[ -f /etc/cron.d/fani-backup ] && FIRST_TIME=0
echo "17 3 * * * root cd $DIR && $PY scripts/backup.py >> /var/log/fani-backup.log 2>&1" > /etc/cron.d/fani-backup
chmod 644 /etc/cron.d/fani-backup
if [ "$FIRST_TIME" = "1" ]; then
  echo "⏳ أول نسخة احتياطية الحين..."
  $PY scripts/backup.py && echo "✅ تم — وصلك ملف النسخة في تلغرام. وبعدها مرة وحدة يوميًا الساعة 3 الفجر."
else
  echo "✅ النسخة الاحتياطية مفعّلة أصلًا — مرة وحدة يوميًا الساعة 3 الفجر (ما سوينا نسخة الحين)."
fi
