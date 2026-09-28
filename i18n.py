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
    "status_line": {
        "ar": "\n\nأنت مسجّل لدينا كفني ({profession}) — حالة طلبك: {status}.",
        "en": "\n\nYou're registered with us as a professional ({profession}) — your status: {status}.",
        "ur": "\n\nآپ ہمارے ہاں بطور کاریگر ({profession}) رجسٹرڈ ہیں — آپ کی حیثیت: {status}۔",
    },
    "free_contacts_line": {
        "ar": "\nاستخدمت {used} من {limit} فرص مجانية. أرسل /subscribe لتفعيل الاشتراك والاستمرار بالظهور بدون حدود.",
        "en": "\nYou've used {used} of {limit} free contacts. Send /subscribe to activate your subscription and keep appearing without limits.",
        "ur": "\nآپ نے {limit} میں سے {used} مفت رابطے استعمال کر لیے۔ لامحدود نظر آنے کے لیے /subscribe بھیجیں۔",
    },
    "subscribed_line": {
        "ar": "\nاشتراكك مفعّل ✅",
        "en": "\nYour subscription is active ✅",
        "ur": "\nآپ کی سبسکرپشن فعال ہے ✅",
    },
    "status_pending": {"ar": "قيد المراجعة", "en": "Under review", "ur": "زیرِ جائزہ"},
    "status_active": {"ar": "نشط", "en": "Active", "ur": "فعال"},
    "status_rejected": {"ar": "مرفوض", "en": "Rejected", "ur": "مسترد"},

    # ─────────────────────────── /register ───────────────────────────
    "reg_start": {
        "ar": "لنبدأ تسجيلك كفني 📝\n\nأرسل اسمك الكامل:",
        "en": "Let's start your registration 📝\n\nSend your full name:",
        "ur": "آئیے آپ کی رجسٹریشن شروع کرتے ہیں 📝\n\nاپنا پورا نام بھیجیں:",
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
        "ar": "ما لقينا مدينة بهذا الاسم. جرّب اسمًا آخر أو اختر من القائمة:",
        "en": "No city found with that name. Try another name or pick from the list:",
        "ur": "اس نام کا کوئی شہر نہیں ملا۔ کوئی اور نام آزمائیں یا فہرست سے منتخب کریں:",
    },
    "reg_district_not_found": {
        "ar": "ما لقينا حيًا بهذا الاسم. جرّب اسمًا آخر أو اختر من القائمة:",
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
        "ar": "تمام، سجّلنا رقمك كـ: {label}",
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
        "ar": "تمام ✅ اختر مجال عملك:",
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
        "ar": "أنت مسجّل بالفعل بمهنة «{profession}» بهذا الحساب.\n\nيسمح بتسجيل مهنة واحدة فقط لكل رقم. إذا كنت تريد تسجيل مهنة أخرى، استخدم جوالًا/حساب تلغرام مختلف.\n\nلتعديل بياناتك الحالية تواصل مع الدعم.",
        "en": "You're already registered with the profession \"{profession}\" on this account.\n\nOnly one profession is allowed per number. If you want to register another profession, use a different phone/Telegram account.\n\nTo edit your current details, contact support.",
        "ur": "آپ پہلے ہی اس اکاؤنٹ پر پیشہ \"{profession}\" کے ساتھ رجسٹرڈ ہیں۔\n\nہر نمبر کے لیے صرف ایک پیشے کی رجسٹریشن کی اجازت ہے۔ اگر آپ دوسرا پیشہ رجسٹر کرنا چاہتے ہیں تو مختلف موبائل/ٹیلیگرام اکاؤنٹ استعمال کریں۔\n\nموجودہ تفصیلات میں ترمیم کے لیے سپورٹ سے رابطہ کریں۔",
    },
    "reg_card_preview_intro": {
        "ar": "👀 هذي بطاقتك اللي بيشوفها العميل بالضبط لما يبحث عن مهنتك:",
        "en": "👀 Here's exactly how your card will look to a customer searching for your profession:",
        "ur": "👀 جب کوئی گاہک آپ کا پیشہ تلاش کرے گا تو آپ کا کارڈ بالکل ایسا نظر آئے گا:",
    },
    "reg_restart": {
        "ar": "تمام، نبدأ التسجيل من جديد.\nأرسل اسمك الكامل:",
        "en": "Okay, let's start the registration over.\nSend your full name:",
        "ur": "ٹھیک ہے، رجسٹریشن دوبارہ شروع کرتے ہیں۔\nاپنا پورا نام بھیجیں:",
    },
    "reg_success": {
        "ar": "✅ تم تسجيلك بنجاح وتفعيل حسابك مباشرة!\n\nالاسم: {name}\nالمدينة: {city}\nالمهنة: {profession}\n\nأنت الآن تظهر للعملاء عند البحث عن هذي المهنة في مدينتك.",
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
        "ar": "اكتب مشكلتك بكلماتك (مثال: «اريد اصلح غسالتي») وسنقترح المهنة المناسبة،\nأو اختر مجال الخدمة مباشرة من القائمة:",
        "en": "Describe your problem in your own words (e.g. \"I need to fix my washing machine\") and we'll suggest the right profession,\nor choose a field directly from the list:",
        "ur": "اپنا مسئلہ اپنے الفاظ میں لکھیں (مثلاً \"مجھے اپنی واشنگ مشین ٹھیک کروانی ہے\") اور ہم موزوں پیشہ تجویز کریں گے،\nیا فہرست سے براہ راست شعبہ منتخب کریں:",
    },
    "srch_no_match": {
        "ar": "لم أستطع التعرف على مشكلتك تلقائيًا 🤔 اختر مجال الخدمة من القائمة:",
        "en": "I couldn't automatically figure out your issue 🤔 Choose a field from the list:",
        "ur": "میں خودکار طور پر آپ کا مسئلہ سمجھ نہیں سکا 🤔 فہرست سے شعبہ منتخب کریں:",
    },
    "srch_smart_match_one": {
        "ar": "يبدو أنك تحتاج: {profession} ✅\n\nاختر منطقتك:",
        "en": "It looks like you need: {profession} ✅\n\nChoose your region:",
        "ur": "لگتا ہے آپ کو ضرورت ہے: {profession} ✅\n\nاپنا علاقہ منتخب کریں:",
    },
    "srch_smart_match_many": {
        "ar": "يبدو أنك تحتاج إحدى هذه المهن، اختر الأنسب:",
        "en": "You might need one of these professions, choose the best fit:",
        "ur": "آپ کو ان میں سے کسی ایک پیشے کی ضرورت ہو سکتی ہے، بہترین آپشن منتخب کریں:",
    },
    "srch_city_step": {
        "ar": "المدينة: {city}\n\nاختر الحي (أو تخطى للبحث بكل المدينة):",
        "en": "City: {city}\n\nChoose a district (or skip to search the whole city):",
        "ur": "شہر: {city}\n\nعلاقہ منتخب کریں (یا پورے شہر میں تلاش کے لیے چھوڑ دیں):",
    },
    "srch_skip_district_btn": {
        "ar": "تخطي (كل أحياء المدينة)",
        "en": "Skip (search whole city)",
        "ur": "چھوڑ دیں (پورے شہر میں تلاش کریں)",
    },
    "srch_no_results": {
        "ar": "لا يوجد حاليًا فنيين ({profession}) متاحين بمدينة «{city}»{district_suffix}.",
        "en": "No professionals ({profession}) are currently available in «{city}»{district_suffix}.",
        "ur": "فی الحال «{city}»{district_suffix} میں کوئی ({profession}) کاریگر دستیاب نہیں۔",
    },
    "srch_results_header": {
        "ar": "وجدنا {count} فني/فنيين ({profession}) بمدينة «{city}»:",
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
        "ar": "استوفينا كل الفنيين بحيك. تحب نبحث لك بحي مجاور؟",
        "en": "We've shown you every professional in your district. Want us to check a nearby district?",
        "ur": "ہم نے آپ کے علاقے کے تمام کاریگر دکھا دیے۔ کیا ہم قریبی علاقے میں تلاش کریں؟",
    },
    "srch_offer_nearby_city": {
        "ar": "ما فيه فنيين أكثر قريبين منك. تحب نبحث لك بأقرب مدينة أو مركز؟",
        "en": "There are no more professionals near you. Want us to check the nearest city or town?",
        "ur": "آپ کے قریب مزید کاریگر نہیں ہیں۔ کیا ہم قریب ترین شہر میں تلاش کریں؟",
    },
    "srch_no_more_suggestions": {
        "ar": "ما فيه مدن أو مراكز أقرب ثانية نقترحها — جرّب /search من جديد بمنطقة مختلفة.",
        "en": "There are no more nearby cities or towns to suggest — try /search again with a different area.",
        "ur": "تجویز کرنے کے لیے مزید قریبی شہر نہیں ہیں — کسی مختلف علاقے کے ساتھ دوبارہ /search آزمائیں۔",
    },
    "srch_end_search_btn": {
        "ar": "❌ إنهاء البحث",
        "en": "❌ End search",
        "ur": "❌ تلاش ختم کریں",
    },
    "srch_ended": {
        "ar": "تمام، تم إنهاء البحث. أرسل /search في أي وقت للبحث من جديد.",
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
        "ar": "⚠️ سيتم حذف كل بياناتك من بوت «فني» نهائيًا وبلا رجعة:\nتسجيلك كفني (إن وجد) وأرقام تواصلك، وسجلات بحثك وتواصلك السابقة.\n\nهل أنت متأكد؟",
        "en": "⚠️ All your data on «Fani» bot will be permanently deleted:\nYour professional registration (if any) and contact numbers, plus your search and contact history.\n\nAre you sure?",
        "ur": "⚠️ «فنی» بوٹ پر آپ کا سارا ڈیٹا مستقل طور پر حذف کر دیا جائے گا:\nآپ کی کاریگر رجسٹریشن (اگر ہو) اور رابطہ نمبرز، نیز آپ کی تلاش اور رابطے کی سابقہ تاریخ۔\n\nکیا آپ کو یقین ہے؟",
    },
    "privacy_confirm_btn": {
        "ar": "✅ نعم، احذف بياناتي نهائيًا",
        "en": "✅ Yes, delete my data permanently",
        "ur": "✅ جی ہاں، میرا ڈیٹا مستقل طور پر حذف کریں",
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
    "privacy_cancelled": {
        "ar": "تم الإلغاء، لم يُحذف شيء.",
        "en": "Cancelled, nothing was deleted.",
        "ur": "منسوخ کر دیا گیا، کچھ حذف نہیں ہوا۔",
    },

    # ─────────────────────────── /help ───────────────────────────
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
            "/help — عرض هذه الرسالة"
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
            "/help — Show this message"
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
            "/help — یہ پیغام دکھائیں"
        ),
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
