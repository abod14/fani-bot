# مصادر بيانات المناطق/المدن/الأحياء لدول التوسع

الملف النهائي `geo.json` يُبنى بالأمر:

```
python data/extra_geo/build_extra_geo.py
```

يدمج القوائم المنشورة التالية (نسخ مختصرة بمجلد `sources/`) — الأسماء منها أولًا، وقائمة
يدوية (`MANUAL` داخل السكربت) تكمّل الأحياء المشهورة الناقصة والإحداثيات غير المتوفرة.

| الملف | الدولة | المصدر | الترخيص |
|---|---|---|---|
| `eg_areas.json` | مصر — 27 محافظة، 410 منطقة | [useswype/egypt-geo-data](https://github.com/useswype/egypt-geo-data) | MIT |
| `oad_eg.json` | مصر — إحداثيات الأقسام/المراكز | [Open Admin Data — Egypt](https://github.com/open-admin-data/egypt-administrative-divisions) | CC BY 4.0 |
| `dubai_communities.json` | دبي — 224 مجتمع رسمي بإحداثياتها | بلدية دبي (Dubai Data, Open Data Licence) عبر [trivoslabs/dubai-communities](https://github.com/trivoslabs/dubai-communities) | Dubai Data Open Data Licence |
| `oad_ae.json` | الإمارات — المدن حسب الإمارة | [Open Admin Data — UAE](https://github.com/open-admin-data/united-arab-emirates-administrative-divisions) | CC BY 4.0 |
| `oad_kw.json` | الكويت — 6 محافظات، 164 منطقة | [Open Admin Data — Kuwait](https://github.com/open-admin-data/kuwait-administrative-divisions) | CC BY 4.0 |
| `oad_bh.json` | البحرين — 4 محافظات، 40 منطقة | [Open Admin Data — Bahrain](https://github.com/open-admin-data/bahrain-administrative-divisions) | CC BY 4.0 |
| `oad_qa.json` | قطر — 8 بلديات، 781 منطقة | [Open Admin Data — Qatar](https://github.com/open-admin-data/qatar-administrative-divisions) | CC BY 4.0 |
| `oad_om.json` | عُمان — 11 محافظة، 49 ولاية | [Open Admin Data — Oman](https://github.com/open-admin-data/oman-administrative-divisions) | CC BY 4.0 |

ملاحظات المعالجة:
- الأجزاء المرقّمة تُدمج باسم واحد (مثل «البرشاء الأولى/الثانية/الثالثة» ← «البرشاء»)، حتى ما
  يضيّع الفني خياراته الخمسة على أجزاء نفس الحي.
- الجزر غير المأهولة والمطارات والموانئ مستبعدة.
- الإحداثيات اللي يكررها المصدر لعدة مناطق (غالبًا مركز المحافظة) تُستبدل بإحداثيات أدق
  من القائمة اليدوية أو من جدول `COORDS` بالسكربت.
