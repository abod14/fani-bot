# ترجمات أسماء المجالات والمهن (إنجليزي/أردو) — العربي يبقى دائمًا المصدر الأساسي
# بعمود name بجدولي domains/professions. تُطبَّق هذي القواميس على قاعدة البيانات
# عبر db.apply_name_translations(...) في كل تشغيل (idempotent).

DOMAIN_TRANSLATIONS = {
    "d1": {"en": "Construction & Building", "ur": "تعمیرات"},
    "d2": {"en": "Electrical & Electronics", "ur": "الیکٹریکل اور الیکٹرانکس"},
    "d3": {"en": "Metalwork & Mechanics", "ur": "دھات کا کام اور مکینکس"},
    "d4": {"en": "Carpentry & Furniture", "ur": "بڑھئی اور فرنیچر"},
    "d5": {"en": "Crafts & Printing", "ur": "دستکاری اور پرنٹنگ"},
    "d6": {"en": "Health & Beauty", "ur": "صحت اور خوبصورتی"},
    "d7": {"en": "Security", "ur": "سیکیورٹی"},
    "d8": {"en": "Business & Consulting", "ur": "کاروبار اور مشاورت"},
    "d9": {"en": "Tech & Computers", "ur": "ٹیکنالوجی اور کمپیوٹر"},
    "d10": {"en": "Pets", "ur": "پالتو جانور"},
    "d11": {"en": "Events", "ur": "تقریبات"},
    "d12": {"en": "Education & Training", "ur": "تعلیم و تربیت"},
    "d13": {"en": "Transport & Delivery", "ur": "ٹرانسپورٹ اور ڈیلیوری"},
    "d14": {"en": "Cleaning", "ur": "صفائی"},
    "d15": {"en": "Gardens & Landscaping", "ur": "باغبانی"},
    "d16": {"en": "Food Services", "ur": "خوراک کی خدمات"},
    "d17": {"en": "Specialized Services", "ur": "خصوصی خدمات"},
}

PROFESSION_TRANSLATIONS = {
    # d1 — البناء والتشييد
    "p1": {"en": "General Builder", "ur": "عام تعمیراتی مزدور"},
    "p2": {"en": "Brick/Block Layer", "ur": "اینٹ/بلاک راج مستری"},
    "p3": {"en": "Stone Mason", "ur": "پتھر تراش"},
    "p4": {"en": "Concrete & Finishing Worker", "ur": "کنکریٹ اور فنشنگ ورکر"},
    "p5": {"en": "Building Carpenter", "ur": "تعمیراتی بڑھئی"},
    "p6": {"en": "Other Structural Worker", "ur": "دیگر ساختی مزدور"},
    "p7": {"en": "Roofing & Insulation Technician", "ur": "چھت اور موصلیت ٹیکنیشن"},
    "p8": {"en": "Tiler", "ur": "ٹائل مستری"},
    "p9": {"en": "Plasterer", "ur": "پلستر مستری"},
    "p10": {"en": "Insulation Technician", "ur": "موصلیت ٹیکنیشن"},
    "p11": {"en": "Glazier", "ur": "شیشہ فٹر"},
    "p12": {"en": "Plumber", "ur": "پلمبر"},
    "p13": {"en": "AC & Refrigeration Technician", "ur": "اے سی اور تبرید ٹیکنیشن"},
    "p14": {"en": "Painter", "ur": "پینٹر"},
    "p15": {"en": "Varnish & Special Coatings Technician", "ur": "وارنش اور خصوصی پینٹ ٹیکنیشن"},
    "p16": {"en": "Building Facade Cleaner", "ur": "عمارت کی صفائی کا ٹیکنیشن"},
    "p55": {"en": "Construction Laborer", "ur": "تعمیراتی مزدور"},
    "p56": {"en": "Marble Technician", "ur": "ماربل ٹیکنیشن"},
    "p65": {"en": "Gypsum Board & Ceiling Technician", "ur": "جپسم بورڈ اور سیلنگ ٹیکنیشن"},

    # d2 — الكهرباء والإلكترونيات
    "p17": {"en": "Home Electrician", "ur": "گھریلو الیکٹریشن"},
    "p18": {"en": "Electrical Mechanics Technician", "ur": "الیکٹریکل میکینکس ٹیکنیشن"},
    "p19": {"en": "Electrical Lines Technician", "ur": "بجلی کی لائنوں کا ٹیکنیشن"},
    "p20": {"en": "Electronics Technician", "ur": "الیکٹرانکس ٹیکنیشن"},
    "p21": {"en": "Networks & Telecom Technician", "ur": "نیٹ ورک اور ٹیلی کام ٹیکنیشن"},
    "p57": {"en": "Water Filter Technician", "ur": "واٹر فلٹر ٹیکنیشن"},
    "p58": {"en": "Home Appliance Technician", "ur": "گھریلو آلات کا ٹیکنیشن"},

    # d3 — المعادن والميكانيكا
    "p22": {"en": "Steel Structure Builder", "ur": "اسٹیل ڈھانچہ ساز"},
    "p23": {"en": "Blacksmith", "ur": "لوہار"},
    "p24": {"en": "Car Mechanic", "ur": "کار مکینک"},
    "p25": {"en": "Industrial/Agricultural Equipment Technician", "ur": "صنعتی اور زرعی آلات کا ٹیکنیشن"},
    "p59": {"en": "Aluminum Technician", "ur": "ایلومینیم ٹیکنیشن"},
    "p60": {"en": "Auto Body Repair Technician", "ur": "گاڑی کی باڈی مرمت ٹیکنیشن"},

    # d4 — النجارة والأثاث
    "p26": {"en": "Furniture Carpenter", "ur": "فرنیچر بڑھئی"},
    "p27": {"en": "Upholsterer", "ur": "اپہولسٹرر"},
    "p28": {"en": "Tailor", "ur": "درزی"},
    "p29": {"en": "Shoemaker/Cobbler", "ur": "موچی"},

    # d5 — الحرف والطباعة
    "p30": {"en": "Printing Technician", "ur": "پرنٹنگ ٹیکنیشن"},
    "p61": {"en": "Locksmith", "ur": "تالا ساز"},

    # d6 — الصحة والجمال
    "p31": {"en": "Barber/Hairdresser", "ur": "حجام"},
    "p32": {"en": "Hairstylist", "ur": "خواتین ہیئر اسٹائلسٹ"},
    "p33": {"en": "Personal Fitness Trainer", "ur": "پرسنل فٹنس ٹرینر"},

    # d7 — الأمن والحراسة
    "p34": {"en": "Security Guard", "ur": "سیکیورٹی گارڈ"},

    # d8 — الأعمال والاستشارات
    "p35": {"en": "Accountant", "ur": "اکاؤنٹنٹ"},
    "p36": {"en": "Lawyer", "ur": "وکیل"},
    "p41": {"en": "Real Estate Agent", "ur": "رئیل اسٹیٹ ایجنٹ"},
    "p44": {"en": "Architect", "ur": "آرکیٹیکٹ"},
    "p45": {"en": "Civil Engineer", "ur": "سول انجینئر"},
    "p46": {"en": "Interior/Product Designer", "ur": "انٹیریئر ڈیزائنر"},

    # d9 — التقنية والحاسب
    "p37": {"en": "Software Developer", "ur": "سافٹ ویئر ڈویلپر"},
    "p38": {"en": "Website Designer", "ur": "ویب سائٹ ڈیزائنر"},
    "p39": {"en": "Tech Support Technician", "ur": "ٹیک سپورٹ ٹیکنیشن"},

    # d10 — الحيوانات الأليفة
    "p40": {"en": "Veterinarian", "ur": "ویٹرنری ڈاکٹر"},

    # d11 — الفعاليات والمناسبات
    "p42": {"en": "Photographer", "ur": "فوٹوگرافر"},
    "p43": {"en": "Event Planner", "ur": "ایونٹ آرگنائزر"},

    # d12 — التعليم والتدريب
    "p47": {"en": "Private Language Tutor", "ur": "پرائیویٹ لینگویج ٹیوٹر"},
    "p48": {"en": "Private Tutor (General Subjects)", "ur": "پرائیویٹ ٹیوٹر"},

    # d13 — النقل والتوصيل
    "p49": {"en": "Car/Van Driver", "ur": "کار/وین ڈرائیور"},
    "p50": {"en": "Truck Driver", "ur": "ٹرک ڈرائیور"},
    "p51": {"en": "Motorcycle Delivery Driver", "ur": "موٹر سائیکل ڈیلیوری ڈرائیور"},
    "p64": {"en": "Furniture Mover", "ur": "فرنیچر شفٹنگ"},

    # d14 — التنظيف
    "p52": {"en": "House Cleaner", "ur": "گھریلو صفائی ملازم"},

    # d15 — حدائق ومسطحات
    "p53": {"en": "Gardener", "ur": "مالی"},

    # d16 — الأغذية والتموين
    "p54": {"en": "Kitchen Helper", "ur": "کچن ہیلپر"},

    # d17 — خدمات متخصصة
    "p62": {"en": "Pool Technician", "ur": "سوئمنگ پول ٹیکنیشن"},
    "p63": {"en": "Pest Control Technician", "ur": "پیسٹ کنٹرول ٹیکنیشن"},
    # مهن أضافها المالك (db.EXTRA_PROFESSIONS)
    "p69": {"en": "Satellite & CCTV Technician", "ur": "ڈش اور سی سی ٹی وی ٹیکنیشن"},
    "p70": {"en": "Dishwasher Repair", "ur": "ڈش واشر مرمت"},
    "p71": {"en": "Oven Repair", "ur": "اوون مرمت"},
    "p72": {"en": "Formwork Carpenter", "ur": "شٹرنگ کارپینٹر"},
    # مهن أُضيفت لاحقًا بملف المهن
    "p66": {"en": "Tow Truck (Car Towing)", "ur": "ریکوری وین (گاڑی کھینچنا)"},
    "p67": {"en": "Goods Mover (Local Transport)", "ur": "سامان کی منتقلی (مقامی)"},
    "p68": {"en": "Makeup Artist", "ur": "میک اپ آرٹسٹ"},
}
