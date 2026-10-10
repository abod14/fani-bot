# نصوص واجهة البوت بثلاث لغات: عربي (الافتراضي)، إنجليزي، أردو — لدعم تعدد لغات
# الفنيين (عربي/إنجليزي/أردو) المطلوب. أسماء المدن/الأحياء السعودية تبقى عربية
# دائمًا (بيانات رسمية) بغض النظر عن لغة الواجهة المختارة — هذا قرار صريح ونهائي.
#
# t(key, lang, **kwargs) يرجّع النص المطلوب، ويرجع للعربي تلقائيًا لو الترجمة أو
# المفتاح غير موجود (حتى ما تطلع رسالة فاضية لأي مستخدم أبدًا).

TEXTS: dict[str, dict[str, str]] = {
    "lang_prompt": {
        "ar": "🌐 اختر لغتك:",
        "en": "🌐 Choose your language:",
        "ur": "🌐 اپنی زبان منتخب کریں:",
    },
    "lang_saved": {
        "ar": "تم اختيار العربية ✅",
        "en": "English selected ✅",
        "ur": "اردو منتخب کر لی گئی ✅",
    },

    # ─────────────────────────── /start ───────────────────────────
    "welcome": {
        "ar": "أهلًا بك في بوت «فني» 👋\n\nبوت «فني» يربط العملاء بمهنيين وفنيين في أكثر من 60 مهنة بمختلف المدن.\n\nاختر ما يناسبك:",
        "en": "Welcome to «Fani» bot 👋\n\n«Fani» connects customers with professionals in 60+ professions across different cities.\n\nChoose an option:",
        "ur": "«فنی» بوٹ میں خوش آمدید 👋\n\n«فنی» گاہکوں کو 60 سے زیادہ پیشوں کے کاریگروں سے مختلف شہروں میں ملاتا ہے۔\n\nاپنی مطلوبہ چیز منتخب کریں:",
    },
    "menu_search": {
        "ar": "🔍 البحث عن فني",
        "en": "🔍 Find a professional",
        "ur": "🔍 کاریگر تلاش کریں",
    },
    "menu_register": {
        "ar": "📝 التسجيل كفني",
        "en": "📝 Register as a professional",
        "ur": "📝 کاریگر کے طور پر رجسٹر کریں",
    },
    "menu_channel": {
        "ar": "📢 قناتنا على تلغرام",
        "en": "📢 Our Telegram channel",
        "ur": "📢 ہمارا ٹیلیگرام چینل",
    },
    "reg_channel_gate": {
        "ar": "قبل إكمال تسجيلك كفنّي، يجب أن تكون مشتركًا في قناتنا على تلغرام أولًا 📢\n\n١) اضغط \"اشترك في القناة\"\n٢) بعد الاشتراك، عُد واضغط \"تحققت، أكمل\"",
        "en": "Before we continue your registration, please join our Telegram channel first 📢\n\n1) Tap \"Join the channel\"\n2) After joining, come back and tap \"I joined, continue\"",
        "ur": "رجسٹریشن جاری رکھنے سے پہلے، پہلے ہمارے ٹیلیگرام چینل میں شامل ہوں 📢\n\n١) \"چینل میں شامل ہوں\" دبائیں\n٢) شامل ہونے کے بعد واپس آکر \"شامل ہو گیا، جاری رکھیں\" دبائیں",
    },
    "reg_channel_join_btn": {
        "ar": "📢 اشترك في القناة",
        "en": "📢 Join the channel",
        "ur": "📢 چینل میں شامل ہوں",
    },
    "reg_channel_check_btn": {
        "ar": "✅ تحققت، أكمل",
        "en": "✅ I joined, continue",
        "ur": "✅ شامل ہو گیا، جاری رکھیں",
    },
    "reg_channel_not_joined": {
        "ar": "لم يظهر اشتراكك في القناة بعد 🤔\nتأكد أنك ضغطت \"اشترك\" فعلًا في القناة، ثم جرّب زر \"تحققت\" مرة أخرى.",
        "en": "It looks like you haven't joined the channel yet 🤔\nMake sure you actually joined, then try \"I joined, continue\" again.",
        "ur": "لگتا ہے آپ ابھی تک چینل میں شامل نہیں ہوئے 🤔\nیقینی بنائیں کہ آپ شامل ہو چکے ہیں، پھر دوبارہ کوشش کریں۔",
    },
    "status_line": {
        "ar": "\n\nأنت مسجّل لدينا كفني ({profession}) — حالة طلبك: {status}.",
        "en": "\n\nYou're registered with us as a professional ({profession}) — your status: {status}.",
        "ur": "\n\nآپ ہمارے ہاں بطور کاریگر ({profession}) رجسٹرڈ ہیں — آپ کی حیثیت: {status}۔",
    },
    "free_contacts_line": {
        "ar": "\nاستخدمت {used} من {limit} فرص مجانية. أرسل /subscribe لتفعيل الاشتراك والاستمرار في الظهور دون حدود.",
        "en": "\nYou've used {used} of {limit} free contacts. Send /subscribe to activate your subscription and keep appearing without limits.",
        "ur": "\nآپ نے {limit} میں سے {used} مفت رابطے استعمال کر لیے۔ لامحدود نظر آنے کے لیے /subscribe بھیجیں۔",
    },
    "subscribed_line": {
        "ar": "\nاشتراكك مفعّل ✅",
        "en": "\nYour subscription is active ✅",
        "ur": "\nآپ کی سبسکرپشن فعال ہے ✅",
    },
    "dual_role_hint": {
        "ar": "\n\n👇 هذا لا يمنعك من استخدام البوت كعميل أيضًا بالحساب نفسه — اضغط زر «🔍 البحث عن فني» أدناه في أي وقت تريد فيه البحث عن فنّي آخر.",
        "en": "\n\n👇 This doesn't stop you from also using the bot as a customer with the same account — tap \"🔍 Find a professional\" below anytime you want to search for someone else.",
        "ur": "\n\n👇 یہ آپ کو اسی اکاؤنٹ سے بطور گاہک بوٹ استعمال کرنے سے نہیں روکتا — جب چاہیں کسی اور کاریگر کی تلاش کے لیے نیچے \"🔍 کاریگر تلاش کریں\" دبائیں۔",
    },
    "status_pending": {"ar": "قيد المراجعة", "en": "Under review", "ur": "زیرِ جائزہ"},
    "status_active": {"ar": "نشط", "en": "Active", "ur": "فعال"},
    "status_rejected": {"ar": "مرفوض", "en": "Rejected", "ur": "مسترد"},

    # ─────────────────────────── /register ───────────────────────────
    "reg_start": {
        "ar": "لنبدأ تسجيلك كفني 📝\n\nأرسل اسمك الكامل بالحروف العربية أو الإنجليزية (لا بحروف الأوردو) — ليسهل على العملاء قراءته والتواصل معك:",
        "en": "Let's start your registration 📝\n\nSend your full name in Arabic or English letters — so customers can read it and contact you easily. E.g. Mohammed Ahmed:",
        "ur": "آئیے آپ کی رجسٹریشن شروع کرتے ہیں 📝\n\nاپنا پورا نام عربی یا انگریزی حروف میں بھیجیں — اردو حروف میں نہیں — تاکہ گاہک اسے پڑھ سکیں اور آسانی سے آپ سے رابطہ کر سکیں۔ مثلاً: Mohammed Ahmed:",
    },
    "reg_name_arabic": {
        "ar": "✍️ نعتذر، نطلب الاسم بالحروف العربية أو الإنجليزية فقط حتى يسهل على العملاء قراءته والتواصل معك. اكتبه هكذا مثلًا: محمد أحمد أو Mohammed Ahmed 🙏",
        "en": "✍️ Sorry, please write your name in Arabic or English letters only, so customers can read it and contact you easily. E.g.: Mohammed Ahmed 🙏",
        "ur": "✍️ معذرت، ہمیں آپ کا نام صرف عربی یا انگریزی حروف میں چاہیے تاکہ گاہک آسانی سے آپ سے رابطہ کر سکیں۔ مثلاً: Mohammed Ahmed 🙏",
    },
    "reg_name_short": {
        "ar": "الاسم قصير جدًا، أرسل اسمك الكامل من فضلك:",
        "en": "That name is too short, please send your full name:",
        "ur": "یہ نام بہت مختصر ہے، براہ کرم اپنا پورا نام بھیجیں:",
    },
    "reg_ask_region": {
        "ar": "اختر منطقتك:",
        "en": "Choose your region:",
        "ur": "اپنا علاقہ منتخب کریں:",
    },
    "reg_region_selected": {
        "ar": "المنطقة: {region}\n\nاختر مدينتك:",
        "en": "Region: {region}\n\nChoose your city:",
        "ur": "علاقہ: {region}\n\nاپنا شہر منتخب کریں:",
    },
    "reg_district_step": {
        "ar": "المدينة: {city}\n\nاختر أحياءك (حي واحد على الأقل، وحتى {max} أحياء كحد أقصى)، ثم اضغط «تأكيد الاختيار»:",
        "en": "City: {city}\n\nChoose your districts (at least 1, up to {max}), then press \"Confirm\":",
        "ur": "شہر: {city}\n\nاپنے علاقے منتخب کریں (کم از کم 1، زیادہ سے زیادہ {max})، پھر \"تصدیق کریں\" دبائیں:",
    },
    "reg_confirm_selection_btn": {
        "ar": "تأكيد الاختيار ✅ ({count}/{max})",
        "en": "Confirm ✅ ({count}/{max})",
        "ur": "تصدیق کریں ✅ ({count}/{max})",
    },
    "reg_min_district_alert": {
        "ar": "اختر حيًا واحدًا على الأقل قبل المتابعة.",
        "en": "Choose at least one district before continuing.",
        "ur": "آگے بڑھنے سے پہلے کم از کم ایک علاقہ منتخب کریں۔",
    },
    "reg_max_district_alert": {
        "ar": "لا يمكن اختيار أكثر من {max} أحياء.",
        "en": "You can't select more than {max} districts.",
        "ur": "آپ {max} سے زیادہ علاقے منتخب نہیں کر سکتے۔",
    },
    "reg_city_not_found": {
        "ar": "لم نجد مدينة بهذا الاسم. جرّب اسمًا آخر أو اختر من القائمة:",
        "en": "No city found with that name. Try another name or pick from the list:",
        "ur": "اس نام کا کوئی شہر نہیں ملا۔ کوئی اور نام آزمائیں یا فہرست سے منتخب کریں:",
    },
    "reg_district_not_found": {
        "ar": "لم نجد حيًا بهذا الاسم. جرّب اسمًا آخر أو اختر من القائمة:",
        "en": "No district found with that name. Try another name or pick from the list:",
        "ur": "اس نام کا کوئی علاقہ نہیں ملا۔ کوئی اور نام آزمائیں یا فہرست سے منتخب کریں:",
    },
    "matched_results": {
        "ar": "النتائج المطابقة:",
        "en": "Matching results:",
        "ur": "مماثل نتائج:",
    },
    "back_to_regions_btn": {
        "ar": "⬅️ رجوع للمناطق",
        "en": "⬅️ Back to regions",
        "ur": "⬅️ علاقوں کی طرف واپس",
    },
    "reg_ask_contact_number": {
        "ar": "أرسل رقم التواصل الخاص بك (مع رمز الدولة)، مثال:\n+966501234567",
        "en": "Send your contact number (with country code), example:\n+966501234567",
        "ur": "اپنا رابطہ نمبر (ملکی کوڈ سمیت) بھیجیں، مثال:\n+966501234567",
    },
    # ─────────────────────────── مهنة ثانية / المدينة كاملة ───────────────────────────
    "reg_second_prof_prompt": {
        "ar": "مهنتك: {profession} ✅\n\nهل تعمل في مهنة ثانية؟ يمكنك إضافة مهنة ثانية واحدة (اختياري)، لتظهر للعملاء في المهنتين.",
        "en": "Your profession: {profession} ✅\n\nDo you work in a second profession? You can add one more (optional) and appear to customers under both.",
        "ur": "آپ کا پیشہ: {profession} ✅\n\nکیا آپ دوسرا پیشہ بھی کرتے ہیں؟ آپ ایک اور پیشہ شامل کر سکتے ہیں (اختیاری) اور دونوں میں نظر آئیں گے۔",
    },
    "reg_add_second_btn": {"ar": "➕ إضافة مهنة ثانية", "en": "➕ Add a second profession", "ur": "➕ دوسرا پیشہ شامل کریں"},
    "reg_no_second_btn": {"ar": "لا، أكمل ✅", "en": "No, continue ✅", "ur": "نہیں، آگے بڑھیں ✅"},
    "reg_skip_second_btn": {"ar": "⏭️ بدون مهنة ثانية", "en": "⏭️ No second profession", "ur": "⏭️ دوسرا پیشہ نہیں"},
    "reg_pick_second_prof": {
        "ar": "اختر مهنتك الثانية:",
        "en": "Choose your second profession:",
        "ur": "اپنا دوسرا پیشہ منتخب کریں:",
    },
    "reg_whole_city_btn": {"ar": "🌍 أغطي المدينة كاملة", "en": "🌍 I cover the whole city", "ur": "🌍 میں پورے شہر میں کام کرتا ہوں"},
    "reg_rare_whole_city_hint": {
        "ar": "🌍 مهنتك من المهن المطلوبة على مستوى المدينة — يمكنك الضغط على «أغطي المدينة كاملة» لتظهر لأي عميل في المدينة، أو اختيار أحياء محددة.",
        "en": "🌍 Your profession can cover the whole city — tap \"I cover the whole city\" to appear to any customer in the city, or pick specific districts.",
        "ur": "🌍 آپ کا پیشہ پورے شہر کا احاطہ کر سکتا ہے — \"میں پورے شہر میں کام کرتا ہوں\" دبائیں یا مخصوص علاقے منتخب کریں۔",
    },
    "reg_reselect_districts_note": {
        "ar": "ℹ️ خيار «المدينة كاملة» متاح للمهن النادرة فقط — اختر أحياءك من جديد:",
        "en": "ℹ️ \"Whole city\" is only available for rare professions — please pick your districts again:",
        "ur": "ℹ️ \"پورا شہر\" صرف نایاب پیشوں کے لیے ہے — براہ کرم اپنے علاقے دوبارہ منتخب کریں:",
    },
    "reg_contact_saved": {"ar": "تم ✅", "en": "Done ✅", "ur": "ہو گیا ✅"},

    # ─────────────────────────── دعوة الزملاء ───────────────────────────
    "menu_invite": {
        "ar": "🎁 ادعُ زملاءك واكسب فرصًا مجانية",
        "en": "🎁 Invite colleagues & earn free contacts",
        "ur": "🎁 ساتھیوں کو مدعو کریں اور مفت مواقع حاصل کریں",
    },
    "ref_invite_msg": {
        "ar": "🎁 ادعُ زملاءك في المهنة!\nعن كل فنّي يسجّل من رابطك تحصل على {bonus} فرص مجانية إضافية.\n\nرابطك الخاص:\n{link}\n\nاضغط زر المشاركة وأرسله إلى زملائك أو إلى مجموعة مهنتك 👇",
        "en": "🎁 Invite your fellow professionals!\nFor every professional who registers through your link, you get {bonus} extra free contacts.\n\nYour personal link:\n{link}\n\nTap a share button and send it to colleagues or your trade group 👇",
        "ur": "🎁 اپنے ہم پیشہ ساتھیوں کو مدعو کریں!\nآپ کے لنک سے رجسٹر ہونے والے ہر کاریگر پر آپ کو {bonus} اضافی مفت مواقع ملیں گے۔\n\nآپ کا خاص لنک:\n{link}\n\nشیئر بٹن دبائیں اور ساتھیوں یا اپنے گروپ کو بھیجیں 👇",
    },
    "ref_stats_line": {
        "ar": "حتى الآن: دعوت {count} من الفنيين وكسبت {earned} من الفرص المجانية 👏",
        "en": "So far: you invited {count} professionals and earned {earned} free contacts 👏",
        "ur": "اب تک: آپ نے {count} کاریگر مدعو کیے اور {earned} مفت مواقع حاصل کیے 👏",
    },
    "ref_share_wa_btn": {"ar": "📤 شارك عبر واتساب", "en": "📤 Share via WhatsApp", "ur": "📤 واٹس ایپ پر شیئر کریں"},
    "ref_share_tg_btn": {"ar": "📤 شارك عبر تلغرام", "en": "📤 Share via Telegram", "ur": "📤 ٹیلیگرام پر شیئر کریں"},
    "ref_share_text": {
        "ar": "السلام عليكم 👋 سجّلت في بوت «فني» على تلغرام — يصلك العملاء مباشرة عبر واتساب، دون عمولة، والتسجيل مجاني الآن. سجّل من هنا:\n{link}",
        "en": "Hi 👋 I registered on the «Fani» Telegram bot — customers reach you directly on WhatsApp, no commission, and registration is free now. Register here:\n{link}",
        "ur": "السلام علیکم 👋 میں نے ٹیلیگرام پر «فنی» بوٹ میں رجسٹر کیا — گاہک براہِ راست واٹس ایپ پر رابطہ کرتے ہیں، کوئی کمیشن نہیں، اور رجسٹریشن ابھی مفت ہے۔ یہاں سے رجسٹر کریں:\n{link}",
    },
    "ref_share_text_short": {
        "ar": "سجّل معي في بوت «فني» — يصلك العملاء عبر واتساب دون عمولة، والتسجيل مجاني الآن 👷‍♂️",
        "en": "Join me on «Fani» — customers reach you on WhatsApp, no commission, free registration now 👷‍♂️",
        "ur": "«فنی» میں میرے ساتھ شامل ہوں — گاہک واٹس ایپ پر رابطہ کرتے ہیں، کوئی کمیشن نہیں 👷‍♂️",
    },
    "ref_credited_notice": {
        "ar": "🎉 زميلك {name} ({profession}) سجّل من رابطك!\nأضفنا لك {bonus} فرص مجانية إضافية.\nمجموع دعواتك: {count}",
        "en": "🎉 Your colleague {name} ({profession}) registered through your link!\nWe added {bonus} extra free contacts to your account.\nTotal invites: {count}",
        "ur": "🎉 آپ کے ساتھی {name} ({profession}) نے آپ کے لنک سے رجسٹر کیا!\nہم نے آپ کو {bonus} اضافی مفت مواقع دیے۔\nکل دعوتیں: {count}",
    },
    "ref_disabled": {
        "ar": "خاصية دعوة الزملاء متوقفة حاليًا 🙏 يمكنك مشاركة رابط البوت مع أي شخص: https://t.me/FanniServiceBot",
        "en": "Inviting colleagues is no longer available 🙏 You can share the bot link with anyone: https://t.me/FanniServiceBot",
        "ur": "ساتھیوں کو مدعو کرنے کی سہولت اب دستیاب نہیں 🙏 آپ بوٹ کا لنک کسی کے ساتھ بھی شیئر کر سکتے ہیں: https://t.me/FanniServiceBot",
    },
    "ref_not_registered": {
        "ar": "رابط الدعوة متاح للفنيين المسجّلين — سجّل أولًا عبر /register",
        "en": "Invite links are for registered professionals — register first via /register",
        "ur": "دعوتی لنک رجسٹرڈ کاریگروں کے لیے ہے — پہلے /register سے رجسٹر کریں",
    },

    # ─────────────────────────── تعدد الدول ───────────────────────────
    "ask_country": {
        "ar": "اختر الدولة 🌍:",
        "en": "Choose your country 🌍:",
        "ur": "اپنا ملک منتخب کریں 🌍:",
    },
    "reg_ask_country_work": {
        "ar": "🌍 اختر الدولة التي تعمل فيها حاليًا:",
        "en": "🌍 Choose the country where you currently work:",
        "ur": "🌍 وہ ملک منتخب کریں جہاں آپ اس وقت کام کرتے ہیں:",
    },
    "srch_ask_country": {
        "ar": "🌍 اختر الدولة التي تبحث فيها عن فني:",
        "en": "🌍 Choose the country where you need a professional:",
        "ur": "🌍 وہ ملک منتخب کریں جہاں آپ کو کاریگر چاہیے:",
    },
    "change_country_btn": {
        "ar": "🌍 تغيير الدولة",
        "en": "🌍 Change country",
        "ur": "🌍 ملک تبدیل کریں",
    },
    "reg_ask_contact_number_country": {
        "ar": "أرسل رقم جوالك للتواصل ({country})، مثال:\n{example}",
        "en": "Send your contact mobile number ({country}), example:\n{example}",
        "ur": "رابطے کے لیے اپنا موبائل نمبر بھیجیں ({country})، مثال:\n{example}",
    },
    "reg_invalid_number_country": {
        "ar": "رقم غير صحيح. أرسل رقم جوال صحيح ({country})، مثال:\n{example}",
        "en": "Invalid number. Send a valid mobile number ({country}), example:\n{example}",
        "ur": "غلط نمبر۔ درست موبائل نمبر بھیجیں ({country})، مثال:\n{example}",
    },
    "reg_city_whole_selected": {
        "ar": "المدينة: {city} ✅\nتغطيتك: المدينة كاملة 🌍",
        "en": "City: {city} ✅\nYour coverage: the whole city 🌍",
        "ur": "شہر: {city} ✅\nآپ کی کوریج: پورا شہر 🌍",
    },
    "sub_stars_only_note": {
        "ar": "الدفع في دولتك متاح حاليًا عبر نجوم تلغرام ⭐ فقط.",
        "en": "Payment in your country is currently available via Telegram Stars ⭐ only.",
        "ur": "آپ کے ملک میں ادائیگی فی الحال صرف ٹیلیگرام اسٹارز ⭐ کے ذریعے دستیاب ہے۔",
    },

    "reg_invalid_number": {
        "ar": "رقم غير صحيح. أرسل الرقم مع رمز الدولة، مثال:\n+966501234567",
        "en": "Invalid number. Send it with the country code, example:\n+966501234567",
        "ur": "غلط نمبر۔ ملکی کوڈ سمیت نمبر بھیجیں، مثال:\n+966501234567",
    },
    "reg_ask_has_whatsapp": {
        "ar": "هل هذا الرقم مفعّل عليه واتساب؟ (بعض العملاء يفضّلون التواصل بواتساب مباشرة)",
        "en": "Is WhatsApp active on this number? (Some customers prefer contacting via WhatsApp directly)",
        "ur": "کیا اس نمبر پر واٹس ایپ فعال ہے؟ (کچھ گاہک براہ راست واٹس ایپ پر رابطہ کرنا پسند کرتے ہیں)",
    },
    "has_whatsapp_yes_btn": {
        "ar": "نعم، مفعّل عليه واتساب ✅",
        "en": "Yes, WhatsApp is active ✅",
        "ur": "جی ہاں، واٹس ایپ فعال ہے ✅",
    },
    "has_whatsapp_no_btn": {
        "ar": "لا، للاتصال فقط 📞",
        "en": "No, calls only 📞",
        "ur": "نہیں، صرف کال کے لیے 📞",
    },
    "reg_wa_saved": {
        "ar": "حسنًا، تم تسجيل رقمك: {label}",
        "en": "Got it, saved your number as: {label}",
        "ur": "ٹھیک ہے، آپ کا نمبر یوں محفوظ کر لیا گیا: {label}",
    },
    "wa_label_yes": {
        "ar": "واتساب مفعّل ✅",
        "en": "WhatsApp active ✅",
        "ur": "واٹس ایپ فعال ✅",
    },
    "wa_label_no": {
        "ar": "رقم اتصال فقط (بدون واتساب) 📞",
        "en": "Calls only (no WhatsApp) 📞",
        "ur": "صرف کال کے لیے (واٹس ایپ کے بغیر) 📞",
    },
    "reg_ask_telegram_contact": {
        "ar": "الآن شارك رقم حسابك بتلغرام بالضغط على الزر بالأسفل:",
        "en": "Now share your Telegram phone number using the button below:",
        "ur": "اب نیچے دیے گئے بٹن سے اپنا ٹیلیگرام نمبر شیئر کریں:",
    },
    "reg_telegram_share_btn": {
        "ar": "📱 مشاركة رقم التلغرام",
        "en": "📱 Share Telegram number",
        "ur": "📱 ٹیلیگرام نمبر شیئر کریں",
    },
    "reg_telegram_retry": {
        "ar": "الرجاء الضغط على زر مشاركة رقم التلغرام بالأسفل (وليس كتابة الرقم يدويًا):",
        "en": "Please press the share-number button below (don't type the number manually):",
        "ur": "براہ کرم نیچے دیا گیا بٹن دبائیں (نمبر خود سے نہ لکھیں):",
    },
    "reg_domain_prompt": {
        "ar": "حسنًا ✅ اختر مجال عملك:",
        "en": "Great ✅ Choose your field of work:",
        "ur": "ٹھیک ہے ✅ اپنا شعبہ منتخب کریں:",
    },
    "domains_available": {
        "ar": "المجالات المتاحة:",
        "en": "Available fields:",
        "ur": "دستیاب شعبے:",
    },
    "reg_domain_selected": {
        "ar": "مجال: {domain}\n\nاختر مهنتك:",
        "en": "Field: {domain}\n\nChoose your profession:",
        "ur": "شعبہ: {domain}\n\nاپنا پیشہ منتخب کریں:",
    },
    "reg_profession_prompt": {
        "ar": "اختر مهنتك من القائمة (مقسّمة حسب المجال):",
        "en": "Choose your profession from the list (grouped by field):",
        "ur": "فہرست سے اپنا پیشہ منتخب کریں (شعبے کے مطابق تقسیم شدہ):",
    },
    "reg_all_professions_list": {
        "ar": "كل المهن المتاحة:",
        "en": "All available professions:",
        "ur": "تمام دستیاب پیشے:",
    },
    "back_to_domain_btn": {
        "ar": "⬅️ رجوع لاختيار المجال",
        "en": "⬅️ Back to field selection",
        "ur": "⬅️ شعبے کے انتخاب کی طرف واپس",
    },
    "unknown_option": {
        "ar": "خيار غير معروف، حاول مرة أخرى.",
        "en": "Unknown option, please try again.",
        "ur": "نامعلوم آپشن، دوبارہ کوشش کریں۔",
    },
    "reg_services_prompt": {
        "ar": "مهنة: {profession}\n\nاختر الخدمات التي تقدّمها (يمكن اختيار أكثر من خدمة):",
        "en": "Profession: {profession}\n\nChoose the services you offer (you can pick more than one):",
        "ur": "پیشہ: {profession}\n\nاپنی خدمات منتخب کریں (ایک سے زیادہ منتخب کر سکتے ہیں):",
    },
    "reg_services_done_btn": {
        "ar": "تأكيد الاختيار ✅",
        "en": "Confirm selection ✅",
        "ur": "انتخاب کی تصدیق کریں ✅",
    },
    "reg_summary_title": {
        "ar": "مراجعة بيانات التسجيل:",
        "en": "Review your registration:",
        "ur": "اپنی رجسٹریشن کا جائزہ لیں:",
    },
    "reg_summary_body": {
        "ar": "الاسم: {name}\nالمدينة: {city}\nالأحياء: {districts}\nرقم التواصل: {contact} ({wa_label})\nحساب التلغرام: {telegram}\nالمهنة: {profession}\nالخدمات: {services}",
        "en": "Name: {name}\nCity: {city}\nDistricts: {districts}\nContact number: {contact} ({wa_label})\nTelegram: {telegram}\nProfession: {profession}\nServices: {services}",
        "ur": "نام: {name}\nشہر: {city}\nعلاقے: {districts}\nرابطہ نمبر: {contact} ({wa_label})\nٹیلیگرام: {telegram}\nپیشہ: {profession}\nخدمات: {services}",
    },
    "reg_city_wide_prompt": {
        "ar": "مهنتك من المهن التي تحتاج إلى تغطية أوسع 🌍\n\nهل تريد تغطية مدينة {city} كاملة (بدلًا من الأحياء التي اخترتها فقط)؟ بذلك تظهر لأي عميل يبحث من أي حي في المدينة.",
        "en": "Your profession needs wider coverage 🌍\n\nWould you like to cover all of {city} (instead of just the districts you picked)? This way you'll show up for customers searching from any district in the city.",
        "ur": "آپ کے پیشے کو زیادہ کوریج کی ضرورت ہے 🌍\n\nکیا آپ پورے {city} کو کور کرنا چاہتے ہیں (صرف منتخب علاقوں کی بجائے)؟",
    },
    "reg_city_wide_yes_btn": {
        "ar": "🌍 نعم، المدينة كاملة",
        "en": "🌍 Yes, the whole city",
        "ur": "🌍 جی ہاں، پورا شہر",
    },
    "reg_city_wide_no_btn": {
        "ar": "📍 لا، الأحياء التي اخترتها",
        "en": "📍 No, just the districts I picked",
        "ur": "📍 نہیں، صرف منتخب علاقے",
    },
    "reg_summary_whole_city": {
        "ar": "المدينة كاملة 🌍",
        "en": "The whole city 🌍",
        "ur": "پورا شہر 🌍",
    },
    "not_specified": {
        "ar": "لم يُحدد", "en": "Not specified", "ur": "غیر متعین",
    },
    "no_services": {
        "ar": "لا يوجد", "en": "None", "ur": "کوئی نہیں",
    },
    "not_available": {
        "ar": "غير متاح", "en": "Not available", "ur": "دستیاب نہیں",
    },
    "reg_confirm_btn": {
        "ar": "✅ تأكيد التسجيل",
        "en": "✅ Confirm registration",
        "ur": "✅ رجسٹریشن کی تصدیق کریں",
    },
    "reg_edit_btn": {
        "ar": "🔧 تعديل المهنة فقط",
        "en": "🔧 Edit profession only",
        "ur": "🔧 صرف پیشہ میں ترمیم کریں",
    },
    "reg_edit_all_btn": {
        "ar": "🔄 تعديل الكل (البدء من جديد)",
        "en": "🔄 Edit everything (start over)",
        "ur": "🔄 سب کچھ تبدیل کریں (دوبارہ شروع کریں)",
    },
    "reg_edit_profession_note": {
        "ar": "يسمح باختيار مهنة واحدة فقط لكل رقم.\nإذا كنت تعمل بأكثر من مهنة، سجّل لكل مهنة من جوال/رقم مختلف.\n\nاختر مجال الخدمة:",
        "en": "Only one profession is allowed per number.\nIf you work in more than one profession, register each one from a different phone/number.\n\nChoose a service field:",
        "ur": "ہر نمبر کے لیے صرف ایک پیشہ منتخب کرنے کی اجازت ہے۔\nاگر آپ ایک سے زیادہ پیشوں میں کام کرتے ہیں تو ہر پیشے کے لیے مختلف موبائل نمبر سے رجسٹر کریں۔\n\nخدمت کا شعبہ منتخب کریں:",
    },
    "reg_back_to_profession_btn": {
        "ar": "◀️ رجوع لقائمة المهن",
        "en": "◀️ Back to professions",
        "ur": "◀️ پیشوں کی فہرست پر واپس جائیں",
    },
    "reg_already_registered": {
        "ar": "أنت مسجّل بالفعل بهذا الحساب ({profession}).\n\nلتعديل بياناتك أو مهنك تواصل مع الدعم.",
        "en": "You're already registered on this account ({profession}).\n\nTo edit your details or professions, contact support.",
        "ur": "آپ پہلے ہی اس اکاؤنٹ پر رجسٹرڈ ہیں ({profession})۔\n\nتفصیلات یا پیشوں میں ترمیم کے لیے سپورٹ سے رابطہ کریں۔",
    },
    "reg_card_preview_intro": {
        "ar": "👀 هذه بطاقتك كما سيراها العميل تمامًا عند البحث عن مهنتك:",
        "en": "👀 Here's exactly how your card will look to a customer searching for your profession:",
        "ur": "👀 جب کوئی گاہک آپ کا پیشہ تلاش کرے گا تو آپ کا کارڈ بالکل ایسا نظر آئے گا:",
    },
    "reg_restart": {
        "ar": "حسنًا، لنبدأ التسجيل من جديد.\nأرسل اسمك الكامل بالحروف العربية أو الإنجليزية (لا بحروف الأوردو) — ليسهل على العملاء قراءته والتواصل معك:",
        "en": "Okay, let's start the registration over.\nSend your full name in Arabic or English letters — so customers can read it and contact you easily. E.g. Mohammed Ahmed:",
        "ur": "ٹھیک ہے، رجسٹریشن دوبارہ شروع کرتے ہیں۔\nاپنا پورا نام عربی یا انگریزی حروف میں بھیجیں — اردو حروف میں نہیں — تاکہ گاہک اسے پڑھ سکیں اور آسانی سے آپ سے رابطہ کر سکیں۔ مثلاً: Mohammed Ahmed:",
    },
    "reg_success": {
        "ar": "✅ تم تسجيلك بنجاح وتفعيل حسابك مباشرة!\n\nالاسم: {name}\nالمدينة: {city}\nالمهنة: {profession}\n\nأنت الآن تظهر للعملاء عند البحث عن هذه المهنة في مدينتك.",
        "en": "✅ You're registered and activated right away!\n\nName: {name}\nCity: {city}\nProfession: {profession}\n\nYou now appear to customers searching for this profession in your city.",
        "ur": "✅ آپ کامیابی سے رجسٹر اور فوری طور پر فعال ہو گئے ہیں!\n\nنام: {name}\nشہر: {city}\nپیشہ: {profession}\n\nاب آپ اپنے شہر میں اس پیشے کی تلاش کرنے والے گاہکوں کو نظر آئیں گے۔",
    },
    "reg_cancelled": {
        "ar": "تم إلغاء التسجيل. أرسل /register في أي وقت للبدء من جديد.",
        "en": "Registration cancelled. Send /register anytime to start again.",
        "ur": "رجسٹریشن منسوخ کر دی گئی۔ دوبارہ شروع کرنے کے لیے کبھی بھی /register بھیجیں۔",
    },

    # ─────────────────────────── /search ───────────────────────────
    "srch_entry": {
        "ar": "اختر المهنة المطلوبة من القائمة:\n\n(للعودة إلى القائمة الرئيسية في أي وقت، اضغط /start)",
        "en": "Choose your profession from the list:\n\n(To go back to the main menu anytime, press /start)",
        "ur": "فہرست سے اپنا پیشہ منتخب کریں:\n\n(کسی بھی وقت مرکزی مینو پر واپس جانے کے لیے /start دبائیں)",
    },
    "srch_no_match": {
        "ar": "لم أستطع التعرف على مشكلتك تلقائيًا 🤔 اختر المهنة المطلوبة من القائمة:",
        "en": "I couldn't automatically figure out your issue 🤔 Choose your profession from the list:",
        "ur": "میں خودکار طور پر آپ کا مسئلہ سمجھ نہیں سکا 🤔 فہرست سے اپنا پیشہ منتخب کریں:",
    },
    "srch_smart_match_one": {
        "ar": "يبدو أنك تحتاج: {profession} ✅",
        "en": "It looks like you need: {profession} ✅",
        "ur": "لگتا ہے آپ کو ضرورت ہے: {profession} ✅",
    },
    "srch_subservice_prompt": {
        "ar": "اختر الخدمة المحدّدة التي تحتاجها من «{profession}» (أو اختر «كل الخدمات» إذا لم تكن متأكدًا):",
        "en": "Choose the specific service you need from \"{profession}\" (or pick \"All services\" if unsure):",
        "ur": "\"{profession}\" میں سے اپنی مطلوبہ مخصوص سروس منتخب کریں (یا غیر یقینی صورت میں \"تمام سروسز\" منتخب کریں):",
    },
    "srch_svc_all_btn": {
        "ar": "📋 كل الخدمات",
        "en": "📋 All services",
        "ur": "📋 تمام سروسز",
    },
    "srch_svc_done_btn": {
        "ar": "✅ تم",
        "en": "✅ Done",
        "ur": "✅ ہو گیا",
    },
    "srch_back_to_professions_btn": {
        "ar": "◀️ رجوع لقائمة المهن",
        "en": "◀️ Back to professions list",
        "ur": "◀️ پیشوں کی فہرست پر واپس",
    },
    "stale_session_alert": {
        "ar": "⏰ انتهت مهلة هذه الجلسة بسبب التأخر في الرد",
        "en": "⏰ This session expired because you took too long to respond",
        "ur": "⏰ جواب دینے میں تاخیر کی وجہ سے یہ سیشن ختم ہو گیا",
    },
    "stale_session_restart": {
        "ar": (
            "⏰ انتهت مهلة هذه المحادثة بسبب التأخر في الرد (بعد فترة من عدم النشاط "
            "نحذف الخطوات القديمة تلقائيًا).\n\n"
            "لا مشكلة — ابدأ من جديد بإرسال {command}\n"
            "أو اضغط /start للعودة إلى القائمة الرئيسية"
        ),
        "en": (
            "⏰ This conversation expired because you took too long to respond "
            "(we automatically clear old steps after a period of inactivity).\n\n"
            "No problem — just start again by sending {command}\n"
            "Or press /start to go back to the main menu"
        ),
        "ur": (
            "⏰ جواب دینے میں تاخیر کی وجہ سے یہ گفتگو ختم ہو گئی (غیر فعالیت کی ایک "
            "مدت کے بعد ہم پرانے مراحل خودکار طور پر صاف کر دیتے ہیں)۔\n\n"
            "کوئی مسئلہ نہیں — بس {command} بھیج کر دوبارہ شروع کریں\n"
            "یا مرکزی مینو پر واپس جانے کے لیے /start دبائیں"
        ),
    },
    "srch_district_choice_prompt": {
        "ar": (
            "كيف تريد تحديد حيّك؟\n\n"
            "💡 إذا ضغطت «شارك موقعي الحالي» ولم يعمل الزر أو ظهر لك خطأ، "
            "فعّل صلاحية الموقع (Location) لتطبيق تلغرام من إعدادات جوالك، ثم أعد المحاولة."
        ),
        "en": (
            "How would you like to specify your district?\n\n"
            "💡 If \"Share my current location\" doesn't work or shows an error, "
            "enable Location permission for the Telegram app in your phone's settings, then try again."
        ),
        "ur": (
            "آپ اپنا علاقہ کیسے متعین کرنا چاہیں گے؟\n\n"
            "💡 اگر \"میری موجودہ لوکیشن شیئر کریں\" کام نہ کرے یا خرابی دکھائے، تو اپنے فون "
            "کی سیٹنگز میں ٹیلیگرام ایپ کے لیے لوکیشن کی اجازت فعال کریں، پھر دوبارہ کوشش کریں۔"
        ),
    },
    "srch_share_location_btn": {
        "ar": "📍 شارك موقعي الحالي",
        "en": "📍 Share my current location",
        "ur": "📍 میری موجودہ لوکیشن شیئر کریں",
    },
    "srch_manual_district_btn": {
        "ar": "🏘️ اختيار الحي يدويًا",
        "en": "🏘️ Choose district manually",
        "ur": "🏘️ دستی طور پر علاقہ منتخب کریں",
    },
    "srch_location_matched": {
        "ar": "📍 حددنا حيّك الأقرب: {district}\nنبحث لك الآن عن أقرب الفنيين...",
        "en": "📍 We matched your nearest district: {district}\nSearching for the nearest professionals now...",
        "ur": "📍 ہم نے آپ کا قریب ترین علاقہ متعین کر لیا: {district}\nاب قریب ترین کاریگر تلاش کیے جا رہے ہیں...",
    },
    "srch_location_no_match": {
        "ar": "لم نتمكن من تحديد حيّك من الموقع المُرسل (بيانات الأحياء غير مكتملة لهذه المدينة حاليًا). اختر حيّك يدويًا:",
        "en": "We couldn't match a district from the location you shared (district data isn't complete for this city yet). Choose your district manually:",
        "ur": "ہم آپ کی بھیجی گئی لوکیشن سے علاقہ متعین نہیں کر سکے (اس شہر کے لیے علاقوں کا ڈیٹا ابھی مکمل نہیں)۔ اپنا علاقہ دستی طور پر منتخب کریں:",
    },
    "srch_smart_match_many": {
        "ar": "يبدو أنك تحتاج إحدى هذه المهن، اختر الأنسب:",
        "en": "You might need one of these professions, choose the best fit:",
        "ur": "آپ کو ان میں سے کسی ایک پیشے کی ضرورت ہو سکتی ہے، بہترین آپشن منتخب کریں:",
    },
    "srch_location_choice_intro": {
        "ar": "حسنًا ✅",
        "en": "Got it ✅",
        "ur": "ٹھیک ہے ✅",
    },
    "srch_location_choice_prompt": {
        "ar": (
            "كيف تريد أن نحدد موقعك؟\n\n"
            "📍 «شارك موقعي الحالي» يحدد لك المدينة والحي مباشرة بضغطة واحدة.\n"
            "🗂️ «اختيار يدوي» إذا كنت تفضّل اختيار المنطقة والمدينة والحي بنفسك.\n\n"
            "💡 إذا ضغطت «شارك موقعي الحالي» ولم يعمل الزر أو ظهر لك خطأ، "
            "فعّل صلاحية الموقع (Location) لتطبيق تلغرام من إعدادات جوالك، ثم أعد المحاولة."
        ),
        "en": (
            "How would you like us to determine your location?\n\n"
            "📍 \"Share my current location\" sets your city and district in one tap.\n"
            "🗂️ \"Choose manually\" if you'd rather pick the region, city and district yourself.\n\n"
            "💡 If \"Share my current location\" doesn't work or shows an error, "
            "enable Location permission for the Telegram app in your phone's settings, then try again."
        ),
        "ur": (
            "آپ چاہتے ہیں ہم آپ کی لوکیشن کیسے متعین کریں؟\n\n"
            "📍 \"میری موجودہ لوکیشن شیئر کریں\" ایک ہی ٹیپ میں شہر اور علاقہ متعین کر دیتا ہے۔\n"
            "🗂️ \"دستی انتخاب\" اگر آپ خود علاقہ، شہر اور محلہ منتخب کرنا چاہیں۔\n\n"
            "💡 اگر \"میری موجودہ لوکیشن شیئر کریں\" کام نہ کرے یا خرابی دکھائے، تو اپنے فون "
            "کی سیٹنگز میں ٹیلیگرام ایپ کے لیے لوکیشن کی اجازت فعال کریں، پھر دوبارہ کوشش کریں۔"
        ),
    },
    "srch_manual_location_btn": {
        "ar": "🗂️ اختيار يدوي",
        "en": "🗂️ Choose manually",
        "ur": "🗂️ دستی انتخاب",
    },
    "srch_location_received": {
        "ar": "📍 تم استلام موقعك، جارٍ تحديده...",
        "en": "📍 Location received, one moment while we match it...",
        "ur": "📍 لوکیشن موصول ہو گئی، ذرا انتظار کریں...",
    },
    "srch_location_confirm_district_line": {
        "ar": "\n🏘️ الحي: {district}",
        "en": "\n🏘️ District: {district}",
        "ur": "\n🏘️ علاقہ: {district}",
    },
    "srch_location_confirm": {
        "ar": "حددنا موقعك تقريبيًا:\n\n🏙️ المدينة: {city}{district_line}\n\nهل هذا صحيح؟",
        "en": "We matched your approximate location:\n\n🏙️ City: {city}{district_line}\n\nIs this correct?",
        "ur": "ہم نے آپ کی تقریبی لوکیشن متعین کی:\n\n🏙️ شہر: {city}{district_line}\n\nکیا یہ درست ہے؟",
    },
    "srch_location_confirm_yes_btn": {
        "ar": "نعم، هذا هو",
        "en": "Yes, that's it",
        "ur": "جی ہاں",
    },
    "srch_location_confirm_no_btn": {
        "ar": "🏘️ لا، اختيار يدوي",
        "en": "🏘️ No, choose manually",
        "ur": "🏘️ نہیں، دستی انتخاب",
    },
    "srch_location_confirmed": {
        "ar": "✅ تم تأكيد الموقع: {city}\nنبحث لك الآن عن أقرب الفنيين...",
        "en": "✅ Location confirmed: {city}\nSearching for the nearest professionals now...",
        "ur": "✅ لوکیشن کی تصدیق ہو گئی: {city}\nاب قریب ترین کاریگر تلاش کیے جا رہے ہیں...",
    },
    "srch_location_select_at_least_one": {
        "ar": "حدّد حيًا واحدًا على الأقل قبل الضغط على «تم»، أو اختر «كل أحياء المدينة».",
        "en": "Mark at least one district before pressing done, or choose \"All districts in the city\".",
        "ur": "تم دبانے سے پہلے کم از کم ایک علاقہ منتخب کریں، یا \"شہر کے تمام علاقے\" چنیں۔",
    },
    "srch_manual_choice_btn": {
        "ar": "🗂️ اختيار يدوي",
        "en": "🗂️ Choose manually",
        "ur": "🗂️ دستی انتخاب",
    },
    "srch_all_city_districts_btn": {
        "ar": "🏙️ كل أحياء المدينة",
        "en": "🏙️ All districts in the city",
        "ur": "🏙️ شہر کے تمام علاقے",
    },
    "srch_city_step": {
        "ar": "المدينة: {city}\n\nاختر الحي (أو تخطَّ هذه الخطوة للبحث في المدينة كلها):",
        "en": "City: {city}\n\nChoose a district (or skip to search the whole city):",
        "ur": "شہر: {city}\n\nعلاقہ منتخب کریں (یا پورے شہر میں تلاش کے لیے چھوڑ دیں):",
    },
    "srch_skip_district_btn": {
        "ar": "تخطي (كل أحياء المدينة)",
        "en": "Skip (search whole city)",
        "ur": "چھوڑ دیں (پورے شہر میں تلاش کریں)",
    },
    "srch_no_results": {
        "ar": "لا يوجد حاليًا فنيون متاحون ({profession}) في مدينة «{city}»{district_suffix}.",
        "en": "No professionals ({profession}) are currently available in «{city}»{district_suffix}.",
        "ur": "فی الحال «{city}»{district_suffix} میں کوئی ({profession}) کاریگر دستیاب نہیں۔",
    },
    "notify_off_btn": {"ar": "🔕 إيقاف الإشعارات", "en": "🔕 Stop notifications", "ur": "🔕 اطلاعات بند کریں"},
    "notify_off_done": {
        "ar": "🔕 تم إيقاف الإشعارات. إذا أردت إعادة تفعيلها فتواصل مع إدارة «فنّي».",
        "en": "🔕 Notifications stopped. Contact Fanni support if you want them back.",
        "ur": "🔕 اطلاعات بند کر دی گئیں۔ دوبارہ چاہیں تو «فنّی» انتظامیہ سے رابطہ کریں۔",
    },
    "free_contacts_exhausted": {
        "ar": "⚠️ انتهت فرصك المجانية للتواصل مع العملاء في «فنّي».\n\nجدد اشتراكك من هنا 👇",
        "en": "⚠️ You've used all your free contacts ({limit}) on Fanni — from now on customers searching for your service won't see you.\n\nSubscribe to show up again with unlimited customers 👇",
        "ur": "⚠️ «فنّی» پر آپ کے مفت رابطے ({limit}) ختم ہو گئے — اب سے آپ کی سروس تلاش کرنے والے گاہکوں کو آپ نظر نہیں آئیں گے۔\n\nدوبارہ نظر آنے اور لامحدود گاہکوں کے لیے سبسکرائب کریں 👇",
    },
    "srch_missed_nudge": {
        "ar": "🔔 يبحث عميل الآن عن «{profession}» في {city}{district_suffix}، لكن رقمك لم يظهر له لأن فرصك المجانية انتهت.\n\nاشترك الآن لتظهر لجميع العملاء الذين يبحثون عن خدمتك 👇",
        "en": "🔔 A customer is searching for \"{profession}\" in {city}{district_suffix} right now, but you didn't show up because you've used up your free contacts.\n\nSubscribe now to appear to every customer searching for your service 👇",
        "ur": "🔔 ابھی ایک گاہک {city}{district_suffix} میں \"{profession}\" تلاش کر رہا ہے، لیکن آپ کا نمبر نظر نہیں آیا کیونکہ آپ کی مفت رابطے ختم ہو چکے ہیں۔\n\nاب سبسکرائب کریں تاکہ آپ ہر تلاش کرنے والے گاہک کو نظر آئیں 👇",
    },
    "srch_missed_nudge_subscribe_btn": {
        "ar": "⭐ اشترك الآن",
        "en": "⭐ Subscribe now",
        "ur": "⭐ ابھی سبسکرائب کریں",
    },
    "srch_recent_note": {
        "ar": "هؤلاء هم الفنيون الذين عرضناهم لك في هذه المهنة خلال آخر 24 ساعة، ويمكنك البحث عن فنيين آخرين بعد انقضائها.",
        "en": "These are the technicians we showed you for this trade in the last 24 hours. You can search for other technicians once that period ends.",
        "ur": "یہ وہی ٹیکنیشن ہیں جو ہم نے پچھلے 24 گھنٹوں میں اس پیشے کے لیے آپ کو دکھائے تھے۔ یہ مدت ختم ہونے کے بعد آپ دوسرے ٹیکنیشن تلاش کر سکتے ہیں۔",
    },
    "srch_places_limit": {
        "ar": 'بحثت في مكانين عن هذه المهنة خلال آخر 24 ساعة، وهو الحد المسموح به. يمكنك البحث في مكان آخر بعد انقضائها، أو البحث من جديد في أحد المكانين لترى الفنيين أنفسهم.',
        "en": 'You have searched two places for this trade in the last 24 hours, which is the limit. You can search another place once that period ends, or search one of the two places again to see the same technicians.',
        "ur": 'آپ نے پچھلے 24 گھنٹوں میں اس پیشے کے لیے دو جگہوں پر تلاش کی ہے، جو حد ہے۔ یہ مدت ختم ہونے کے بعد آپ کسی اور جگہ تلاش کر سکتے ہیں، یا انہی دو جگہوں میں سے کسی ایک میں دوبارہ تلاش کر کے وہی ٹیکنیشن دیکھ سکتے ہیں۔',
    },
    'rt_ask_one': {
        "ar": 'مرحبًا 👋\nتواصلتَ {when} عبر «فنّي» مع {name} ({prof}).\nهل تعاملتَ معه؟',
        "en": 'Hello 👋\nYou contacted {name} ({prof}) via «Fanni» {when}.\nDid you deal with him?',
        "ur": 'السلام علیکم 👋\nآپ نے {when} «فنّی» کے ذریعے {name} ({prof}) سے رابطہ کیا تھا۔\nکیا آپ نے ان سے کام کروایا؟',
    },
    'rt_ask_many': {
        "ar": 'مرحبًا 👋\nتواصلتَ {when} عبر «فنّي» مع عدد من الفنيين.\nمع أيّهم تعاملت؟',
        "en": 'Hello 👋\nYou contacted several technicians via «Fanni» {when}.\nWhich one did you deal with?',
        "ur": 'السلام علیکم 👋\nآپ نے {when} «فنّی» کے ذریعے کئی ٹیکنیشنز سے رابطہ کیا تھا۔\nآپ نے کس سے کام کروایا؟',
    },
    'rt_today': {
        "ar": 'اليوم',
        "en": 'today',
        "ur": 'آج',
    },
    'rt_yesterday': {
        "ar": 'أمس',
        "en": 'yesterday',
        "ur": 'کل',
    },
    'rt_yes': {
        "ar": 'نعم',
        "en": 'Yes',
        "ur": 'ہاں',
    },
    'rt_no': {
        "ar": 'لا',
        "en": 'No',
        "ur": 'نہیں',
    },
    'rt_none': {
        "ar": 'لم أتعامل مع أحد',
        "en": 'None of them',
        "ur": 'کسی سے نہیں',
    },
    'rt_how': {
        "ar": 'كيف تقيّم عمل {name}؟',
        "en": "How would you rate {name}'s work?",
        "ur": 'آپ {name} کے کام کو کیسی ریٹنگ دیں گے؟',
    },
    'rt_s5': {
        "ar": 'ممتاز',
        "en": 'Excellent',
        "ur": 'بہترین',
    },
    'rt_s4': {
        "ar": 'جيد جدًا',
        "en": 'Very good',
        "ur": 'بہت اچھا',
    },
    'rt_s3': {
        "ar": 'جيد',
        "en": 'Good',
        "ur": 'اچھا',
    },
    'rt_s2': {
        "ar": 'مقبول',
        "en": 'Acceptable',
        "ur": 'قابل قبول',
    },
    'rt_s1': {
        "ar": 'غير مقبول',
        "en": 'Unacceptable',
        "ur": 'ناقابل قبول',
    },
    'rt_thanks': {
        "ar": 'شكرًا لك 🌟 تقييمك يساعد غيرك على اختيار الفني المناسب.',
        "en": 'Thank you 🌟 Your rating helps others choose the right technician.',
        "ur": 'شکریہ 🌟 آپ کی ریٹنگ دوسروں کو صحیح ٹیکنیشن چننے میں مدد دیتی ہے۔',
    },
    'rt_no_thanks': {
        "ar": 'شكرًا لك 🙏 إذا احتجت فنيًا في أي وقت، اضغط /start.',
        "en": 'Thank you 🙏 Whenever you need a technician, tap /start.',
        "ur": 'شکریہ 🙏 جب بھی ٹیکنیشن کی ضرورت ہو، /start دبائیں۔',
    },
    'rt_expired': {
        "ar": 'انتهت مدة هذا التقييم 🙏',
        "en": 'This rating has expired 🙏',
        "ur": 'اس ریٹنگ کی مدت ختم ہو گئی 🙏',
    },
    'rt_already': {
        "ar": 'سبق أن قيّمت هذا الفني، شكرًا لك 🌟',
        "en": 'You have already rated this technician, thank you 🌟',
        "ur": 'آپ اس ٹیکنیشن کو پہلے ہی ریٹ کر چکے ہیں، شکریہ 🌟',
    },
    "srch_nearest_note": {
        "ar": "لا يوجد حاليًا فنيون في {district}، وهؤلاء الأقرب إليك من الأحياء المجاورة 👇",
        "en": "No technicians in {district} right now — here are the nearest from neighbouring districts 👇",
        "ur": "{district} میں فی الحال کوئی ٹیکنیشن نہیں، یہ قریبی محلوں سے آپ کے قریب ترین ہیں 👇",
    },
    "srch_city_note": {
        "ar": "لم نجد فنيين في {district} ولا في الأحياء المجاورة، وهذه نتائج {city} كاملة 👇",
        "en": "No technicians in {district} or neighbouring districts — here are results for all of {city} 👇",
        "ur": "{district} اور قریبی محلوں میں کوئی ٹیکنیشن نہیں ملا، یہ پورے {city} کے نتائج ہیں 👇",
    },
    "srch_results_header": {
        "ar": "وجدنا {count} من الفنيين ({profession}) في مدينة «{city}»:",
        "en": "We found {count} professional(s) ({profession}) in «{city}»:",
        "ur": "ہمیں «{city}» میں {count} ({profession}) کاریگر ملے:",
    },
    "srch_more_btn": {
        "ar": "عرض المزيد ⬇️ ({remaining} متبقي)",
        "en": "Show more ⬇️ ({remaining} left)",
        "ur": "مزید دکھائیں ⬇️ ({remaining} باقی)",
    },
    "srch_more_prompt": {
        "ar": "للمزيد من الفنيين:",
        "en": "For more professionals:",
        "ur": "مزید کاریگروں کے لیے:",
    },
    "srch_offer_nearby_district": {
        "ar": "عرضنا جميع الفنيين في حيّك. هل تريد البحث في حي مجاور؟",
        "en": "We've shown you every professional in your district. Want us to check a nearby district?",
        "ur": "ہم نے آپ کے علاقے کے تمام کاریگر دکھا دیے۔ کیا ہم قریبی علاقے میں تلاش کریں؟",
    },
    "srch_offer_nearby_city": {
        "ar": "لا يوجد فنيون آخرون قريبون منك. هل تريد البحث في أقرب مدينة أو مركز؟",
        "en": "There are no more professionals near you. Want us to check the nearest city or town?",
        "ur": "آپ کے قریب مزید کاریگر نہیں ہیں۔ کیا ہم قریب ترین شہر میں تلاش کریں؟",
    },
    "srch_no_more_suggestions": {
        "ar": "لا توجد مدن أو مراكز قريبة أخرى نقترحها — جرّب /search من جديد في منطقة مختلفة.",
        "en": "There are no more nearby cities or towns to suggest — try /search again with a different area.",
        "ur": "تجویز کرنے کے لیے مزید قریبی شہر نہیں ہیں — کسی مختلف علاقے کے ساتھ دوبارہ /search آزمائیں۔",
    },
    "srch_end_search_btn": {
        "ar": "❌ إنهاء البحث",
        "en": "❌ End search",
        "ur": "❌ تلاش ختم کریں",
    },
    "srch_ended": {
        "ar": "حسنًا، تم إنهاء البحث. أرسل /search في أي وقت للبحث من جديد.",
        "en": "Alright, search ended. Send /search anytime to search again.",
        "ur": "ٹھیک ہے، تلاش ختم ہو گئی۔ دوبارہ تلاش کے لیے کبھی بھی /search بھیجیں۔",
    },
    "srch_cancelled": {
        "ar": "تم إلغاء البحث. أرسل /search في أي وقت للبدء من جديد.",
        "en": "Search cancelled. Send /search anytime to start again.",
        "ur": "تلاش منسوخ کر دی گئی۔ دوبارہ شروع کرنے کے لیے کبھی بھی /search بھیجیں۔",
    },
    "srch_contact_wa_btn": {
        "ar": "📱 تواصل عبر واتساب",
        "en": "📱 Contact via WhatsApp",
        "ur": "📱 واٹس ایپ پر رابطہ کریں",
    },
    "srch_contact_show_btn": {
        "ar": "📞 عرض رقم التواصل",
        "en": "📞 Show contact number",
        "ur": "📞 رابطہ نمبر دکھائیں",
    },
    "srch_wa_number_text": {
        "ar": "رقم واتساب {name}: {number}",
        "en": "{name}'s WhatsApp number: {number}",
        "ur": "{name} کا واٹس ایپ نمبر: {number}",
    },
    "srch_open_wa_btn": {
        "ar": "💬 فتح واتساب الآن",
        "en": "💬 Open WhatsApp now",
        "ur": "💬 ابھی واٹس ایپ کھولیں",
    },
    "srch_wa_prefill_text": {
        "ar": "مرحبًا، وجدتك عبر بوت «فني» 🛠️ أحتاج خدمة: {profession}",
        "en": "Hi, I found you through the Fani bot 🛠️ I need this service: {profession}",
        "ur": "السلام علیکم، میں نے آپ کو فنی بوٹ کے ذریعے پایا 🛠️ مجھے یہ سروس چاہیے: {profession}",
    },
    "srch_no_wa_text": {
        "ar": "{name} — هذا الرقم بدون واتساب:\n📞 للاتصال المباشر: {number}",
        "en": "{name} — this number has no WhatsApp:\n📞 Call directly: {number}",
        "ur": "{name} — اس نمبر پر واٹس ایپ نہیں ہے:\n📞 براہ راست کال کریں: {number}",
    },
    "srch_telegram_alt": {
        "ar": "✈️ أو تواصل معه عبر تلغرام: {number}",
        "en": "✈️ Or contact them via Telegram: {number}",
        "ur": "✈️ یا ٹیلیگرام پر رابطہ کریں: {number}",
    },
    "srch_contact_tg_btn": {
        "ar": "✈️ تواصل عبر تلغرام",
        "en": "✈️ Contact via Telegram",
        "ur": "✈️ ٹیلیگرام پر رابطہ کریں",
    },
    "srch_open_tg_btn": {
        "ar": "✈️ فتح تلغرام الآن",
        "en": "✈️ Open Telegram now",
        "ur": "✈️ ابھی ٹیلیگرام کھولیں",
    },
    "wa_link_ok": {
        "ar": "✅ تم ربط حسابك في واتساب بتلغرام! ستصلك هنا تنبيهات العملاء مجانًا، ويمكنك إدارة حسابك واشتراكك من هنا.",
        "en": "✅ Your WhatsApp account is now linked to Telegram! You'll get customer alerts here for free and can manage your account and subscription here.",
        "ur": "✅ آپ کا واٹس ایپ اکاؤنٹ ٹیلیگرام سے جڑ گیا! گاہکوں کی اطلاعات یہاں مفت ملیں گی اور آپ اپنا اکاؤنٹ یہاں سے سنبھال سکتے ہیں۔",
    },
    "wa_link_already": {
        "ar": "حسابك مربوط بتلغرام بالفعل ✅",
        "en": "Your account is already linked to Telegram ✅",
        "ur": "آپ کا اکاؤنٹ پہلے سے ٹیلیگرام سے جڑا ہوا ہے ✅",
    },
    "wa_link_linked_other": {
        "ar": "⚠️ هذا التسجيل مربوط بحساب تلغرام آخر.",
        "en": "⚠️ This registration is linked to another Telegram account.",
        "ur": "⚠️ یہ رجسٹریشن کسی دوسرے ٹیلیگرام اکاؤنٹ سے جڑی ہے۔",
    },
    "wa_link_tg_has_account": {
        "ar": "⚠️ حسابك في تلغرام مسجّل كفنّي بالفعل، لذلك لا يمكن ربط تسجيل واتساب به.",
        "en": "⚠️ Your Telegram account is already registered as a professional, so the WhatsApp registration can't be linked to it.",
        "ur": "⚠️ آپ کا ٹیلیگرام اکاؤنٹ پہلے سے کاریگر کے طور پر رجسٹرڈ ہے، اس لیے واٹس ایپ رجسٹریشن نہیں جوڑی جا سکتی۔",
    },
    "wa_link_not_found": {
        "ar": "⚠️ رابط الربط غير صالح. عُد إلى بوت واتساب واضغط «أنا فني» ← «اربط بتلغرام».",
        "en": "⚠️ Invalid link. Go back to the WhatsApp bot and tap «I'm a professional» → «Link Telegram».",
        "ur": "⚠️ لنک درست نہیں۔ واٹس ایپ بوٹ میں «میں کاریگر ہوں» ← «ٹیلیگرام سے جوڑیں» دبائیں۔",
    },
    "srch_wa_open_text": {
        "ar": "اضغط الزر لفتح محادثة واتساب مع {name} 👇",
        "en": "Tap the button to open a WhatsApp chat with {name} 👇",
        "ur": "{name} کے ساتھ واٹس ایپ چیٹ کھولنے کے لیے بٹن دبائیں 👇",
    },
    "srch_tg_open_text": {
        "ar": "اضغط الزر لفتح محادثة تلغرام مع {name} 👇",
        "en": "Tap the button to open a Telegram chat with {name} 👇",
        "ur": "{name} کے ساتھ ٹیلیگرام چیٹ کھولنے کے لیے بٹن دبائیں 👇",
    },
    "link_expired_page": {
        "ar": "انتهت صلاحية هذا الرابط أو أن الفني لم يعد متاحًا. ابحث من جديد في بوت «فني».",
        "en": "This link has expired or the professional is no longer available. Search again in the Fani bot.",
        "ur": "یہ لنک ختم ہو چکا ہے یا کاریگر اب دستیاب نہیں۔ فنی بوٹ میں دوبارہ تلاش کریں۔",
    },
    "link_back_to_bot": {
        "ar": "العودة إلى البوت",
        "en": "Back to the bot",
        "ur": "بوٹ پر واپس جائیں",
    },
    "srch_tg_number_text": {
        "ar": "رقم {name} على تلغرام: {number}\nإذا لم يفتح الرابط المحادثة مباشرة، فاحفظ الرقم في جهات الاتصال وابحث عنه داخل تلغرام.",
        "en": "{name}'s Telegram number: {number}\nIf the link doesn't open the chat directly, save the number in your contacts and search for it inside Telegram.",
        "ur": "{name} کا ٹیلیگرام نمبر: {number}\nاگر لنک براہ راست چیٹ نہ کھولے تو نمبر کو اپنے رابطوں میں محفوظ کریں اور ٹیلیگرام میں تلاش کریں۔",
    },
    "srch_professional_gone": {
        "ar": "عذرًا، هذا الفني لم يعد متاحًا.",
        "en": "Sorry, this professional is no longer available.",
        "ur": "معذرت، یہ کاریگر اب دستیاب نہیں ہے۔",
    },

    # ─────────────────────────── /delete_account ───────────────────────────
    "privacy_no_data": {
        "ar": "لا يوجد لدينا حاليًا أي بيانات مخزّنة باسمك.",
        "en": "We don't currently have any data stored under your name.",
        "ur": "فی الحال آپ کے نام کوئی ڈیٹا محفوظ نہیں ہے۔",
    },
    "privacy_confirm_prompt": {
        "ar": "⚠️ سيتم حذف كل بياناتك من بوت «فني» نهائيًا وبلا رجعة:\nتسجيلك كفني (إن وجد) وأرقام تواصلك، وسجلات بحثك وتواصلك السابقة.\n\nℹ️ إن كنت فنيًا: نحتفظ باسمك ورقمك تسعين يومًا ثم يُحذفان نهائيًا، ويمكنك حذفهما الآن بزر «احذف كل شيء». أما تقييمك فيبقى مرتبطًا برقمك بصورة مشفّرة لا تكشفه، ويعود إليك إن سجّلت من جديد.\n\nهل أنت متأكد؟",
        "en": "⚠️ All your data on «Fani» bot will be permanently deleted:\nYour professional registration (if any) and contact numbers, plus your search and contact history.\n\nℹ️ If you are a technician: we keep your name and number for 90 days, then they are permanently deleted; you can delete them now with the «Delete everything» button. Your rating stays linked to your number in encrypted form (your number is not revealed) and returns to you if you register again.\n\nAre you sure?",
        "ur": "⚠️ «فنی» بوٹ پر آپ کا سارا ڈیٹا مستقل طور پر حذف کر دیا جائے گا:\nآپ کی کاریگر رجسٹریشن (اگر ہو) اور رابطہ نمبرز، نیز آپ کی تلاش اور رابطے کی سابقہ تاریخ۔\n\nℹ️ اگر آپ کاریگر ہیں: ہم آپ کا نام اور نمبر نوے دن تک رکھتے ہیں، پھر یہ ہمیشہ کے لیے حذف ہو جاتے ہیں؛ آپ «سب کچھ حذف کریں» کے بٹن سے انہیں ابھی حذف کر سکتے ہیں۔ آپ کی ریٹنگ آپ کے نمبر سے خفیہ (انکرپٹڈ) شکل میں منسلک رہتی ہے جس سے نمبر ظاہر نہیں ہوتا، اور دوبارہ رجسٹر ہونے پر آپ کو واپس مل جاتی ہے۔\n\nکیا آپ کو یقین ہے؟",
    },
    "privacy_confirm_btn": {
        "ar": "✅ نعم، احذف بياناتي نهائيًا",
        "en": "✅ Yes, delete my data permanently",
        "ur": "✅ جی ہاں، میرا ڈیٹا مستقل طور پر حذف کریں",
    },
    "privacy_confirm_all_btn": {
        "ar": "🧹 احذف كل شيء",
        "en": "🧹 Delete everything",
        "ur": "🧹 سب کچھ حذف کریں",
    },
    "privacy_cancel_btn": {
        "ar": "❌ إلغاء",
        "en": "❌ Cancel",
        "ur": "❌ منسوخ کریں",
    },
    "privacy_deleted": {
        "ar": "✅ تم حذف جميع بياناتك نهائيًا من بوت «فني».\nيمكنك التسجيل أو البحث من جديد في أي وقت بإرسال /start.",
        "en": "✅ All your data has been permanently deleted from «Fani» bot.\nYou can register or search again anytime by sending /start.",
        "ur": "✅ آپ کا سارا ڈیٹا «فنی» بوٹ سے مستقل طور پر حذف کر دیا گیا ہے۔\nآپ کبھی بھی /start بھیج کر دوبارہ رجسٹر یا تلاش کر سکتے ہیں۔",
    },
    "privacy_deleted_pro": {
        "ar": "✅ تم حذف حسابك من «فني»، ولن تظهر للعملاء بعد الآن. يمكنك التسجيل من جديد في أي وقت بإرسال /start.",
        "en": "✅ Your «Fani» account has been deleted and you will no longer appear to customers. You can register again anytime by sending /start.",
        "ur": "✅ «فنی» سے آپ کا اکاؤنٹ ڈیلیٹ ہو گیا، اب آپ گاہکوں کو نظر نہیں آئیں گے۔ آپ کسی بھی وقت /start بھیج کر دوبارہ رجسٹر کر سکتے ہیں۔",
    },
    "delr_question": {
        "ar": "يهمّنا رأيك 🙏 ما سبب حذف حسابك؟ (اختياري)",
        "en": "Your opinion matters to us 🙏 Why did you delete your account? (optional)",
        "ur": "آپ کی رائے ہمارے لیے اہم ہے 🙏 آپ نے اکاؤنٹ کیوں ڈیلیٹ کیا؟ (اختیاری)",
    },
    "delr_few": {"ar": "لم تصلني طلبات كافية", "en": "Not enough requests", "ur": "کافی درخواستیں نہیں آئیں"},
    "delr_fee": {"ar": "رسوم الاشتراك", "en": "Subscription fee", "ur": "سبسکرپشن فیس"},
    "delr_job": {"ar": "تركت هذه المهنة", "en": "I left this profession", "ur": "یہ پیشہ چھوڑ دیا"},
    "delr_move": {"ar": "انتقلت إلى مدينة أخرى", "en": "Moved to another city", "ur": "دوسرے شہر منتقل ہو گیا"},
    "delr_bot": {"ar": "صعوبة في استخدام البوت", "en": "Hard to use the bot", "ur": "بوٹ استعمال کرنا مشکل"},
    "delr_other": {"ar": "سبب آخر (سأكتبه)", "en": "Other (I'll type it)", "ur": "دوسری وجہ (لکھوں گا)"},
    "delr_skip": {"ar": "أفضّل عدم الذكر", "en": "Prefer not to say", "ur": "نہیں بتانا چاہتا"},
    "delr_write": {"ar": "✍️ اكتب السبب في رسالة واحدة:", "en": "✍️ Type the reason in one message:",
                   "ur": "✍️ وجہ ایک پیغام میں لکھیں:"},
    "delr_thanks": {"ar": "شكرًا لك 🌷 نتمنى لك التوفيق.", "en": "Thank you 🌷 We wish you all the best.",
                    "ur": "شکریہ 🌷 ہم آپ کی کامیابی کے لیے دعاگو ہیں۔"},
    "delr_thanks_text": {
        "ar": "شكرًا لك 🌷 وصلنا السبب، وسنستفيد منه في تحسين الخدمة.",
        "en": "Thank you 🌷 We received your reason and will use it to improve the service.",
        "ur": "شکریہ 🌷 آپ کی بتائی ہوئی وجہ ہمیں مل گئی، اس سے ہم سروس بہتر بنائیں گے۔",
    },
    "privacy_cancelled": {
        "ar": "تم الإلغاء، لم يُحذف شيء.",
        "en": "Cancelled, nothing was deleted.",
        "ur": "منسوخ کر دیا گیا، کچھ حذف نہیں ہوا۔",
    },

    # ─────────────────────────── /help ───────────────────────────
    "menu_support": {
        "ar": "💬 تواصل مع الدعم",
        "en": "💬 Contact support",
        "ur": "💬 سپورٹ سے رابطہ",
    },
    "help_text": {
        "ar": (
            "بوت «فني» — دليل المهنيين والفنيين\n\n"
            "الأوامر المتاحة:\n"
            "/start — القائمة الرئيسية\n"
            "/register — التسجيل كفني\n"
            "/search — البحث عن فني\n"
            "/subscribe — تفعيل/تجديد الاشتراك (للفنيين)\n"
            "/language — تغيير لغة الواجهة\n"
            "/delete_account — حذف بياناتك نهائيًا من البوت\n"
            "/cancel — إلغاء أي عملية جارية\n"
            "/help — عرض هذه الرسالة\n\n"
            "💬 الدعم والاستفسارات (واتساب): https://wa.me/966530990046"
        ),
        "en": (
            "«Fani» bot — professionals directory\n\n"
            "Available commands:\n"
            "/start — Main menu\n"
            "/register — Register as a professional\n"
            "/search — Find a professional\n"
            "/subscribe — Activate/renew subscription (for professionals)\n"
            "/language — Change interface language\n"
            "/delete_account — Permanently delete your data\n"
            "/cancel — Cancel any ongoing process\n"
            "/help — Show this message\n\n"
            "💬 Support (WhatsApp): https://wa.me/966530990046"
        ),
        "ur": (
            "«فنی» بوٹ — کاریگروں کی ڈائریکٹری\n\n"
            "دستیاب کمانڈز:\n"
            "/start — مرکزی مینو\n"
            "/register — بطور کاریگر رجسٹر کریں\n"
            "/search — کاریگر تلاش کریں\n"
            "/subscribe — سبسکرپشن فعال/تجدید کریں (کاریگروں کے لیے)\n"
            "/language — زبان تبدیل کریں\n"
            "/delete_account — اپنا ڈیٹا مستقل طور پر حذف کریں\n"
            "/cancel — کوئی بھی جاری عمل منسوخ کریں\n"
            "/help — یہ پیغام دکھائیں\n\n"
            "💬 سپورٹ (واٹس ایپ): https://wa.me/966530990046"
        ),
    },

    # ─────────────────────────── الاشتراك: تفعيل وانتهاء ───────────────────────────
    "sub_activated_card": {
        "ar": (
            "✅ تم تفعيل اشتراكك بنجاح\n\n"
            "📦 المدة: {days} يومًا\n"
            "📅 يبدأ: {start_date}\n"
            "⏳ ينتهي: {expiry_date}\n\n"
            "طوال فترة الاشتراك ستظهر في نتائج البحث دون أي حد لفرص التواصل، وسوف "
            "نرسل لك تنبيهًا هنا في تلغرام قبل انتهاء الاشتراك لتجدده دون انقطاع."
        ),
        "en": (
            "✅ Your subscription is now active\n\n"
            "📦 Duration: {days} days\n"
            "📅 Starts: {start_date}\n"
            "⏳ Ends: {expiry_date}\n\n"
            "You'll appear in search results with no contact-limit for the whole "
            "period, and we'll notify you here on Telegram when it's about to end."
        ),
        "ur": (
            "✅ آپ کی سبسکرپشن فعال ہو گئی\n\n"
            "📦 مدت: {days} دن\n"
            "📅 شروع: {start_date}\n"
            "⏳ ختم: {expiry_date}\n\n"
            "پوری مدت کے دوران آپ بغیر کسی رابطہ کی حد کے تلاش کے نتائج میں نظر آئیں گے، "
            "اور ختم ہونے سے پہلے ہم آپ کو یہاں ٹیلیگرام پر مطلع کریں گے۔"
        ),
    },
    "sub_expired_notice": {
        "ar": (
            "⏰ انتهى اشتراكك في بوت «فني»\n\n"
            "عدت الآن إلى فرص التواصل المجانية المحدودة، وقد تختفي من نتائج "
            "البحث إذا استنفدتها. جدّد اشتراكك الآن لتستمر في الظهور للعملاء دون حدود:"
        ),
        "en": (
            "⏰ Your Fani bot subscription has expired\n\n"
            "You're back on the limited free-contacts tier, and may disappear from "
            "search results if you've used them up. Renew now to keep appearing "
            "with no limits:"
        ),
        "ur": (
            "⏰ آپ کی فنی بوٹ سبسکرپشن ختم ہو گئی\n\n"
            "اب آپ محدود مفت رابطوں کی سطح پر واپس آ گئے ہیں، اور اگر وہ ختم ہو "
            "چکے ہوں تو تلاش کے نتائج سے غائب ہو سکتے ہیں۔ بغیر حد کے نظر آتے "
            "رہنے کے لیے ابھی تجدید کریں:"
        ),
    },
    "sub_renew_btn": {
        "ar": "🔄 تجديد الاشتراك الآن",
        "en": "🔄 Renew subscription now",
        "ur": "🔄 ابھی سبسکرپشن تجدید کریں",
    },
    "donate_prompt": {
        "ar": (
            "🙏 لاحظنا أنك استخدمت بوت «فني» أكثر من {count} مرة — يسعدنا أن نخدمك!\n\n"
            "يتطلب تشغيل البوت وإضافة الفنيين وتصنيفهم وقتًا وجهدًا مستمرين من فريق صغير. "
            "إذا رغبت في دعمنا بمبلغ رمزي، فسنكون شاكرين لك 🙏 (الدعم اختياري تمامًا، ولا يوقف "
            "استخدامك للبوت أبدًا):"
        ),
        "en": (
            "🙏 We noticed you've used the «Fani» bot more than {count} times — glad it's useful!\n\n"
            "Running the bot and listing/categorizing professionals takes ongoing time and "
            "effort from a small team. If you'd like to support us with a small amount, we'd "
            "be grateful 🙏 (completely optional, never blocks your use of the bot):"
        ),
        "ur": (
            "🙏 ہم نے دیکھا کہ آپ نے «فني» بوٹ {count} سے زیادہ بار استعمال کیا — خوشی ہوئی!\n\n"
            "بوٹ چلانا اور کاریگروں کو شامل/درجہ بندی کرنا ایک چھوٹی ٹیم کے لیے مسلسل وقت اور "
            "محنت لیتا ہے۔ اگر آپ ہمیں تھوڑی سی رقم سے سپورٹ کرنا چاہیں تو ہم مشکور ہوں گے 🙏 "
            "(مکمل طور پر اختیاری، آپ کے بوٹ کے استعمال کو کبھی نہیں روکتا):"
        ),
    },
    "donate_amount_btn": {
        "ar": "💙 {sar} ريال",
        "en": "💙 {sar} SAR",
        "ur": "💙 {sar} ریال",
    },
    "donate_dismiss_btn": {
        "ar": "🙏 لا، شكرًا",
        "en": "🙏 No thanks for now",
        "ur": "🙏 ابھی نہیں، شکریہ",
    },
    "donate_dismissed": {
        "ar": "حسنًا، لا مشكلة 🙏 استمتع باستخدام البوت!",
        "en": "No problem at all 🙏 Enjoy using the bot!",
        "ur": "کوئی مسئلہ نہیں 🙏 بوٹ کا استعمال جاری رکھیں!",
    },
    "donate_method_prompt": {
        "ar": "اختر طريقة الدفع لدعمنا بمبلغ {sar} ريال:",
        "en": "Choose a payment method to support us with {sar} SAR:",
        "ur": "{sar} ریال کی سپورٹ کے لیے ادائیگی کا طریقہ منتخب کریں:",
    },
    "donate_tap_btn": {
        "ar": "💳 الدفع عبر Tap (مدى/فيزا/آبل باي)",
        "en": "💳 Pay via Tap (mada/Visa/Apple Pay)",
        "ur": "💳 Tap کے ذریعے ادائیگی",
    },
    "donate_stars_btn": {
        "ar": "⭐ الدفع عبر Telegram Stars — {stars} نجمة",
        "en": "⭐ Pay via Telegram Stars — {stars} stars",
        "ur": "⭐ Telegram Stars کے ذریعے — {stars} اسٹارز",
    },
    "donate_pay_now_btn": {
        "ar": "💳 الدفع الآن",
        "en": "💳 Pay now",
        "ur": "💳 ابھی ادائیگی کریں",
    },
    "donate_verify_btn": {
        "ar": "✅ تحققت من الدفع",
        "en": "✅ I've paid",
        "ur": "✅ ادائیگی ہو گئی",
    },
    "donate_tap_instructions": {
        "ar": "اضغط للدفع عبر Tap، وبعد إتمام الدفع عُد واضغط 'تحققت من الدفع':",
        "en": "Tap to pay via Tap, then come back and press 'I've paid':",
        "ur": "Tap کے ذریعے ادائیگی کے لیے دبائیں، پھر واپس آ کر 'ادائیگی ہو گئی' دبائیں:",
    },
    "donate_tap_not_configured": {
        "ar": "⚠️ الدفع عبر Tap غير مفعّل حاليًا. جرّب الدفع عبر Telegram Stars بدلًا عنه.",
        "en": "⚠️ Tap payments aren't enabled right now. Try Telegram Stars instead.",
        "ur": "⚠️ Tap ادائیگی ابھی فعال نہیں۔ اس کی بجائے Telegram Stars آزمائیں۔",
    },
    "donate_tap_error": {
        "ar": "⚠️ حدث خطأ أثناء الاتصال بـ Tap. حاول مرة أخرى بعد قليل، أو جرّب Stars.",
        "en": "⚠️ Something went wrong contacting Tap. Try again shortly, or use Stars.",
        "ur": "⚠️ Tap سے رابطے میں خرابی ہوئی۔ تھوڑی دیر بعد کوشش کریں یا Stars استعمال کریں۔",
    },
    "donate_tap_verify_error": {
        "ar": "تعذّر التحقق الآن، حاول بعد قليل.",
        "en": "Couldn't verify right now, try again shortly.",
        "ur": "ابھی تصدیق نہیں ہو سکی، تھوڑی دیر بعد کوشش کریں۔",
    },
    "donate_tap_not_paid_yet": {
        "ar": "لم يصلنا تأكيد الدفع بعد. إذا كنت قد دفعت فعلًا، فانتظر دقيقة وجرّب الزر مرة أخرى.",
        "en": "We haven't received payment confirmation yet. If you've already paid, wait a minute and try again.",
        "ur": "ابھی تک ادائیگی کی تصدیق موصول نہیں ہوئی۔ اگر آپ نے ادائیگی کر دی ہے تو ایک منٹ انتظار کریں۔",
    },
    "donate_already_paid": {
        "ar": "تم تسجيل هذا الدعم مسبقًا ✅ شكرًا لك!",
        "en": "This contribution was already recorded ✅ thank you!",
        "ur": "یہ عطیہ پہلے ہی درج ہو چکا ✅ شکریہ!",
    },
    "donate_thanks": {
        "ar": "🙏 شكرًا جزيلًا لدعمك! فهو يساعدنا كثيرًا على مواصلة تطوير بوت «فني» وإضافة فنيين جدد.",
        "en": "🙏 Thank you so much for your support! It really helps us keep improving «Fani» and adding new professionals.",
        "ur": "🙏 آپ کی سپورٹ کا بہت شکریہ! یہ ہمیں «فني» بوٹ بہتر بنانے اور نئے کاریگر شامل کرنے میں مدد دیتا ہے۔",
    },
    "donate_stars_match_error": {
        "ar": "تم استلام الدعم، لكن حدث خطأ في مطابقة الطلب. يُرجى التواصل مع الدعم.",
        "en": "Payment received but there was a matching error. Please contact support.",
        "ur": "ادائیگی موصول ہوئی لیکن مماثلت میں خرابی آئی۔ براہ کرم سپورٹ سے رابطہ کریں۔",
    },
}


def t(key: str, lang: str = "ar", **kwargs) -> str:
    entry = TEXTS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get("ar") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
