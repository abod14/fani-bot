# عدّاد نشاط البوت لمربع "صحة السيرفر" بلوحة التحكم.
#
# كل رسالة/ضغطة زر تُعدّ بالذاكرة فقط (مجموعة مستخدمين لكل دقيقة)، وكل دقيقة تنكتب
# خلاصة الدقائق المنتهية بصف واحد بقاعدة البيانات — يعني ولا كتابة إضافية مع كل
# ضغطة، فما يأثر على سرعة البوت أبدًا.

import asyncio
from datetime import datetime, timezone

import db

_buckets: dict[str, dict] = {}  # minute → {"users": set, "updates": int}


def _minute_key(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M")


async def track_update(update, context):
    user = getattr(update, "effective_user", None)
    key = _minute_key()
    bucket = _buckets.setdefault(key, {"users": set(), "updates": 0})
    bucket["updates"] += 1
    if user:
        bucket["users"].add(user.id)


async def flush_job(context):
    """يكتب كل الدقائق المنتهية (مو الدقيقة الحالية) لقاعدة البيانات ويمسحها من الذاكرة."""
    current = _minute_key()
    done = [k for k in list(_buckets) if k < current]
    for key in done:
        bucket = _buckets.pop(key)
        try:
            await asyncio.to_thread(
                db.record_activity_minute, key, len(bucket["users"]), bucket["updates"]
            )
        except Exception as e:  # noqa: BLE001 — إحصائية فقط، ما نوقف البوت بسببها
            print(f"[activity] تعذّر حفظ نشاط الدقيقة {key}: {e}", flush=True)
