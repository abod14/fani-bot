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
    "dual_role_hint": {
        "ar": "\n\n👇 هذا لا يمنعك من استخدام البوت كعميل أيضًا بنفس الحساب — اضغط زر «🔍 البحث عن فني» تحت في أي وقت تبي تدور على فني ثاني.",
        "en": "\n\n👇 This doesn't stop you from also using the bot as a customer with the same account — tap \"🔍 Find a professional\" below anytime you want to search for someone else.",
        "ur": "\n\n👇 یہ آپ کو اسی اکاؤنٹ سے بطور گاہک بوٹ استعمال کرنے سے نہیں روکتا — جب چاہیں کسی اور کاریگر کی تلاش کے لیے نیچے \"🔍 کاریگر تلاش کریں\" دبائیں۔",
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
        "ar": "اختر مهنتك من القائمة:\n\n(لو تبي ترجع للقائمة الرئيسية بأي وقت، اضغط /start)",
        "en": "Choose your profession from the list:\n\n(To go back to the main menu anytime, press /start)",
        "ur": "فہرست سے اپنا پیشہ منتخب کریں:\n\n(کسی بھی وقت مرکزی مینو پر واپس جانے کے لیے /start دبائیں)",
    },
    "srch_no_match": {
        "ar": "لم أستطع التعرف على مشكلتك تلقائيًا 🤔 اختر مهنتك من القائمة:",
        "en": "I couldn't automatically figure out your issue 🤔 Choose your profession from the list:",
        "ur": "میں خودکار طور پر آپ کا مسئلہ سمجھ نہیں سکا 🤔 فہرست سے اپنا پیشہ منتخب کریں:",
    },
    "srch_smart_match_one": {
        "ar": "يبدو أنك تحتاج: {profession} ✅",
        "en": "It looks like you need: {profession} ✅",
        "ur": "لگتا ہے آپ کو ضرورت ہے: {profession} ✅",
    },
    "srch_subservice_prompt": {
        "ar": "اختر الخدمة المحدّدة اللي تحتاجها من «{profession}» (أو اختر «كل الخدمات» لو مو متأكد):",
        "en": "Choose the specific service you need from \"{profession}\" (or pick \"All services\" if unsure):",
        "ur": "\"{profession}\" میں سے اپنی مطلوبہ مخصوص سروس منتخب کریں (یا غیر یقینی صورت میں \"تمام سروسز\" منتخب کریں):",
    },
    "srch_svc_all_btn": {
        "ar": "📋 كل الخدمات",
        "en": "📋 All services",
        "ur": "📋 تمام سروسز",
    },
    "srch_back_to_professions_btn": {
        "ar": "◀️ رجوع لقائمة المهن",
        "en": "◀️ Back to professions list",
        "ur": "◀️ پیشوں کی فہرست پر واپس",
    },
    "stale_session_alert": {
        "ar": "⏰ خلصت مهلة هذي الجلسة لتأخرك بالرد",
        "en": "⏰ This session expired because you took too long to respond",
        "ur": "⏰ جواب دینے میں تاخیر کی وجہ سے یہ سیشن ختم ہو گیا",
    },
    "stale_session_restart": {
        "ar": (
            "⏰ خلصت مهلة هذي المحادثة لأنك تأخرت بالرد (بعد فترة من عدم النشاط "
            "نمسح الخطوات القديمة تلقائيًا).\n\n"
            "ما فيه مشكلة — بس ابدأ من جديد بإرسال {command}\n"
            "أو اضغط /start للرجوع للقائمة الرئيسية"
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
            "كيف تحب تحدد حيّك؟\n\n"
            "💡 لو ضغطت «شارك موقعي الحالي» وما اشتغل الزر أو ظهر لك خطأ، "
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
        "ar": "ما قدرنا نحدد حيّك من الموقع المُرسل (بيانات الأحياء غير مكتملة لهذي المدينة حاليًا). اختر حيّك يدويًا:",
        "en": "We couldn't match a district from the location you shared (district data isn't complete for this city yet). Choose your district manually:",
        "ur": "ہم آپ کی بھیجی گئی لوکیشن سے علاقہ متعین نہیں کر سکے (اس شہر کے لیے علاقوں کا ڈیٹا ابھی مکمل نہیں)۔ اپنا علاقہ دستی طور پر منتخب کریں:",
    },
    "srch_smart_match_many": {
        "ar": "يبدو أنك تحتاج إحدى هذه المهن، اختر الأنسب:",
        "en": "You might need one of these professions, choose the best fit:",
        "ur": "آپ کو ان میں سے کسی ایک پیشے کی ضرورت ہو سکتی ہے، بہترین آپشن منتخب کریں:",
    },
    "srch_location_choice_intro": {
        "ar": "تمام ✅",
        "en": "Got it ✅",
        "ur": "ٹھیک ہے ✅",
    },
    "srch_location_choice_prompt": {
        "ar": (
            "كيف تحب نحدد موقعك؟\n\n"
            "📍 «شارك موقعي الحالي» تحدد لك المدينة والحي مباشرة بضغطة وحدة.\n"
            "🗂️ «اختيار يدوي» لو تفضل تختار المنطقة والمدينة والحي بنفسك.\n\n"
            "💡 لو ضغطت «شارك موقعي الحالي» وما اشتغل الزر أو ظهر لك خطأ، "
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
        "ar": "📍 تم استلام موقعك، لحظة نحدده...",
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
        "ar": "✅ نعم",
        "en": "✅ Yes",
        "ur": "✅ جی ہاں",
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
    "srch_missed_nudge": {
        "ar": "🔔 فيه عميل الحين يدوّر على «{profession}» في {city}{district_suffix}، لكن رقمك ما ظهر له لأنك خلّصت فرصك المجانية.\n\nاشترك الآن حتى تظهر لكل العملاء اللي يبحثون عن خدمتك 👇",
        "en": "🔔 A customer is searching for \"{profession}\" in {city}{district_suffix} right now, but you didn't show up because you've used up your free contacts.\n\nSubscribe now to appear to every customer searching for your service 👇",
        "ur": "🔔 ابھی ایک گاہک {city}{district_suffix} میں \"{profession}\" تلاش کر رہا ہے، لیکن آپ کا نمبر نظر نہیں آیا کیونکہ آپ کی مفت رابطے ختم ہو چکے ہیں۔\n\nاب سبسکرائب کریں تاکہ آپ ہر تلاش کرنے والے گاہک کو نظر آئیں 👇",
    },
    "srch_missed_nudge_subscribe_btn": {
        "ar": "⭐ اشترك الآن",
        "en": "⭐ Subscribe now",
        "ur": "⭐ ابھی سبسکرائب کریں",
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
    "srch_wa_prefill_text": {
        "ar": "مرحبًا، لقيتك عبر بوت «فني» 🛠️ أحتاج خدمة: {profession}",
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
    "srch_tg_number_text": {
        "ar": "رقم {name} على تلغرام: {number}\nلو الرابط ما فتح المحادثة مباشرة، احفظ الرقم في جهات الاتصال وابحث عنه داخل تلغرام.",
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

    # ─────────────────────────── الاشتراك: تفعيل وانتهاء ───────────────────────────
    "sub_activated_card": {
        "ar": (
            "✅ تم تفعيل اشتراكك بنجاح\n\n"
            "📦 المدة: {days} يوم\n"
            "📅 يبدأ: {start_date}\n"
            "⏳ ينتهي: {expiry_date}\n\n"
            "طول فترة الاشتراك تظهر بنتائج البحث بدون أي حد لفرص التواصل، وراح "
            "نرسل لك تنبيه هنا بتلغرام قبل ما ينتهي الاشتراك حتى تجدده بدون انقطاع."
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
            "رجعت الآن للفرص المجانية المحدودة بالتواصل، وممكن تختفي من نتائج "
            "البحث لو خلصتها. جدّد اشتراكك الآن عشان تستمر تظهر للعملاء بدون حدود:"
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
