# EDUNEXA

**सही स्पेलिंग: EDUNEXA**

## स्ट्रक्चर

```
EDUNEXA/
├── 01_DOCUMENTATION/          ← डॉक्यूमेंट्स, आर्किटेक्चर
├── 02_SOURCE_CODE/
│   ├── CORE/                  ← स्थिर, टेस्टेड कोड (कभी सीधे प्रयोग नहीं)
│   │   ├── id_card/
│   │   ├── exam_paper/
│   │   └── main_assistant/
│   └── DEVELOPING/            ← नया काम / प्रयोग / टेस्टिंग
├── 03_DATABASE/               ← SQLite, Excel, डेटा
├── 04_AI_MODELS/
├── 05_DESIGNS/
├── 06_MEDIA/                  ← फोटो, PDF, फॉन्ट (Git में नहीं)
├── 07_DEPLOYMENT/
├── 08_TESTING/
├── 09_TOOLS/                  ← organize स्क्रिप्ट यहाँ है
└── 10_BACKUP/
```

## इस्तेमाल

1. `09_TOOLS/organize_edunexa.py` को अपने मौजूदा प्रोजेक्ट फोल्डर में कॉपी करें।
2. चलाएं:
   ```
   python organize_edunexa.py
   ```
3. फाइलें अपने आप सही जगह कॉपी हो जाएंगी।

## नियम

- **CORE** = जो प्रोडक्शन में चल रहा है। यहाँ सीधे प्रयोग मत करें।
- **DEVELOPING** = नया फीचर / टेस्टिंग।
- जब DEVELOPING में सफलता मिल जाए → कोड CORE में मर्ज करें।
- भारी फाइलें (images, pdfs) `06_MEDIA` में रहेंगी और Git में नहीं जाएंगी।

## Git सेटअप

```bash
cd EDUNEXA
git init
git add .
git commit -m "Initial EDUNEXA structure with CORE + DEVELOPING"
```

---
Saini School Uniforms & Stationery
