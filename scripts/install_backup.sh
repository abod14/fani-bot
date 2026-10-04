#!/usr/bin/env bash
# يفعّل النسخة الاحتياطية اليومية (الساعة 3 الفجر بتوقيت السيرفر) ويسوي أول نسخة الحين.
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"
PY=$(systemctl show -p ExecStart fani-bot 2>/dev/null | grep -o 'path=[^ ;]*' | head -1 | cut -d= -f2)
[ -x "$PY" ] || PY=$(command -v python3)
echo "17 3 * * * root cd $DIR && $PY scripts/backup.py >> /var/log/fani-backup.log 2>&1" > /etc/cron.d/fani-backup
chmod 644 /etc/cron.d/fani-backup
echo "⏳ أول نسخة احتياطية الحين..."
$PY scripts/backup.py && echo "✅ تم — تفقد تلغرام: وصلك ملف النسخة. والنسخ اليومية بتوصلك كل يوم الساعة 3 الفجر."
