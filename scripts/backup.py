# نسخة احتياطية يومية لقاعدة بيانات «فني» — تُشغّل تلقائيًا كل يوم (cron) عبر scripts/install_backup.sh.
#
# 1) نسخة آمنة من القاعدة (sqlite backup API — صحيحة حتى والبوتات شغالة) مضغوطة في /root/fani-backups
#    (نحتفظ بآخر 14 نسخة).
# 2) ترسلها للأدمن في تلغرام (محادثته مع البوت) — نسخة خارج السيرفر تلقائيًا، لو صار شي للسيرفر.
#
# الاستعادة: انظر آخر الملف.

import gzip
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

import config  # noqa: E402

BACKUP_DIR = Path(os.environ.get("FANI_BACKUP_DIR", "/root/fani-backups"))
KEEP = 14
TELEGRAM_LIMIT = 45 * 1024 * 1024  # حد إرسال الملفات عبر البوت ~50MB


def main():
    if os.environ.get("TURSO_DATABASE_URL"):
        print("Turso DB — has its own backups; skipping.")
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(BACKUP_DIR, 0o700)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    tmp = BACKUP_DIR / f"fani-{stamp}.db"
    src = sqlite3.connect(str(config.DB_PATH), timeout=30)
    dst = sqlite3.connect(str(tmp))
    with dst:
        src.backup(dst)
    stats = dst.execute("SELECT COUNT(*), SUM(status='active') FROM professionals").fetchone()
    src.close()
    dst.close()

    out = BACKUP_DIR / f"fani-{stamp}.db.gz"
    with open(tmp, "rb") as f_in, gzip.open(out, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    tmp.unlink()
    os.chmod(out, 0o600)
    shutil.copyfile(out, BACKUP_DIR / "latest.db.gz")
    os.chmod(BACKUP_DIR / "latest.db.gz", 0o600)

    olds = sorted(BACKUP_DIR.glob("fani-*.db.gz"))
    for old in olds[:-KEEP]:
        old.unlink()

    size = out.stat().st_size
    caption = (f"🗄️ نسخة احتياطية يومية — {datetime.now():%Y-%m-%d}\n"
               f"الفنيين: {stats[0]} (نشط: {stats[1] or 0}) • الحجم: {size // 1024} KB\n"
               "احتفظ بهذا الملف — فيه بيانات الفنيين كلها.")
    api = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
    if size <= TELEGRAM_LIMIT:
        with open(out, "rb") as f:
            r = requests.post(f"{api}/sendDocument", data={"chat_id": config.ADMIN_TELEGRAM_ID, "caption": caption},
                              files={"document": (out.name, f, "application/gzip")}, timeout=120)
    else:
        r = requests.post(f"{api}/sendMessage", timeout=30, data={
            "chat_id": config.ADMIN_TELEGRAM_ID,
            "text": caption + "\n⚠️ الملف أكبر من حد تلغرام، فهو محفوظ على السيرفر فقط — حان وقت نسخ سحابي أكبر."})
    print(f"backup {out.name} {size}B telegram={r.status_code}")


if __name__ == "__main__":
    main()

# ───────── الاستعادة (لو احتجت) ─────────
# 1) ارفع الملف للسيرفر (أو استخدم /root/fani-backups/latest.db.gz)
# 2) systemctl stop fani-bot fani-admin fani-wa
# 3) gunzip -c fani-XXXX.db.gz > /root/fani-bot/fani_bot.db
# 4) systemctl start fani-bot fani-admin fani-wa
