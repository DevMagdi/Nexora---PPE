# دليل استكشاف التشغيل المحلي (Local Run Troubleshooting)

> هذا الدليل مكتوب بالعربية لتشخيص أشهر مشاكل `python -m uvicorn app.main:app --reload`
> على Windows/Linux، وعلى رأسها تحذير `InsecureKeyLengthWarning` والتشغيل مع SQL Server.

---

## 1. اللوج اللي شفته — سطر بسطر و"وصل فين؟"

لوج مثل هذا:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process ... using WatchFiles
INFO:     Started server process ...
INFO:     Waiting for application startup.
2026-10-12 15:23:39 | INFO     | app.main | Starting Nexora PPE API (env=dev)
INFO  [alembic.runtime.migration] Context impl MSSQLImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
.../jwt/api_jwt.py:149: InsecureKeyLengthWarning: The HMAC key is 22 bytes long ...
.../jwt/api_jwt.py:370: InsecureKeyLengthWarning: The HMAC key is 22 bytes long ...
```

معناه:

| السطر | المعنى |
|---|---|
| `Uvicorn running on ...` | سيرفر Uvicorn اشتغل وبيسمع على البورت |
| `Started reloader process` | وضع `--reload` شغال (أي تعديل في الكود يعيد التشغيل) |
| `Waiting for application startup` | Uvicorn مستني الـ `lifespan` بتاع FastAPI يخلص |
| `Starting Nexora PPE API (env=dev)` | التطبيق بدأ فعلًا بوضع التطوير |
| `Context impl MSSQLImpl` | الـ `DATABASE_URL` بتاعك **SQL Server** (مش SQLite الافتراضي) والاتصال بالقاعدة نجح |
| `Will assume transactional DDL` | Alembic بدأ يطبق الـ migrations — رسالة طبيعية مع SQL Server |
| `InsecureKeyLengthWarning ... 22 bytes` | ⚠️ **المشكلة الأساسية**: قيمة `JWT_SECRET` في ملف `.env` قصيرة (22 بايت) بينما HS256 يحتاج **32 بايت على الأقل** (RFC 7518) |

### وصل فين بالظبط؟

التحذيرين بيظهروا **فقط** عند إنشاء/قراءة توكن (`jwt.encode` لحظة الـ login، و`jwt.decode` مع أول طلب موثّق)،
فمعنى ظهورهم إن السيرفر غالبًا **كمّل الـ startup كله بنجاح**: الـ migrations، تجهيز القاعدة، تحميل موديلات
YOLO، وتشغيل الـ camera manager — وبعدها استقبل أول login منك أو من الداشبورد.

بعد الإصلاحات في هذا الفرع، الـ startup بقى يطبع مراحل واضحة تعرف منها "وصل فين" مباشرة:

```text
Starting Nexora PPE API (env=dev)
Database backend: SQL Server (aioodbc)
Applying database migrations...
Database migrations applied
Database schema is up to date
Ensuring bootstrap admin user...
Bootstrap user check complete
Loading detection models (first run can take a while)...
Camera manager started — API is ready
```

لو شفت `Camera manager started — API is ready` وبعدها `Application startup complete` من Uvicorn،
فالسيرفر جاهز تمامًا. ولو وقف قبل سطر معيّن، فالمشكلة في المرحلة اللي بعده مباشرة.

---

## 2. المشاكل اللي كانت في اللوج

### المشكلة 1 (الأساسية): `JWT_SECRET` ضعيف — 22 بايت بدل 32+ ⚠️

- **السبب**: قيمة `JWT_SECRET` في `.env` قصيرة أو نص عادي (مثل `my-dev-secret-12345`).
- **الخطورة**: توكنات الجلسات والـ media تبقى قابلة للتزوير، ونفس المفتاح مستخدم في تشفير بصمات الـ audit.
- **الإصلاح في الكود**: أي قيمة ضعيفة **توقف التشغيل فورًا** برسالة واضحة في كل البيئات (dev/staging/prod)،
  بدل التحذير الغامض اللي كان يظهر متأخرًا مع أول login.

### المشكلة 2: SQL Server محتاج Drivers إضافية

- سطر `MSSQLImpl` معناه إنك مش شغال على SQLite الافتراضية.
- باكدج `requirements/base.txt` لا تشمل `aioodbc/pyodbc`، والـ ODBC Driver نفسه برنامج منفصل من Microsoft.
- **الإصلاح في الكود**: ملف جديد `requirements/mssql.txt` + رسائل خطأ عربية/إنجليزية واضحة عند نقص أي Driver.

### المشكلة 3: `--reload` يراقب كل المجلد (بطء وإعادة تشغيل عشوائية)

- الأمر الافتراضي يراقب كل المشروع بما فيه `.venv` و`violation_frames`، وده على Windows بطيء
  وممكن يعمل reload متكرر.
- **الحل**: راقب `app/` فقط (انظر قسم التشغيل الموصى به بالأسفل).

### المشكلة 4: أسرار dev العشوائية تتغير مع كل reload

- لو `JWT_SECRET`/`BOOTSTRAP_PASSWORD` مش مكتوبين في `.env`، السيرفر يولّد قيمًا عشوائية **تتغير مع كل reload**،
  فتتسجّل خروج تلقائيًا وتتغير كلمة مرور الـ admin المطبوعة في اللوج.
- **الحل**: ثبّت قيمًا قوية في `.env` (انظر الوصفة بالأسفل) — الباسورد المطبوعة لمرة واحدة تتغير إجباريًا عند أول دخول.

---

## 3. الإصلاح خطوة بخطوة (Windows PowerShell)

### الخطوة 1: ثبّت الاعتماديات الأساسية

```powershell
cd C:\Users\devmigo\PycharmProjects\Nexora---PPE
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### الخطوة 2: لو تستخدم SQL Server — ثبّت الـ Drivers

```powershell
pip install -r requirements/mssql.txt
```

ثم ثبّت برنامج **`ODBC Driver 18 for SQL Server`** من موقع Microsoft (مثبّت `.msi` منفصل — ليس باكدج pip)،
وتأكد أن الـ `DATABASE_URL` في `.env` بهذا الشكل:

```env
DATABASE_URL=mssql+aioodbc://USER:PASSWORD@HOST:1433/DBNAME?driver=ODBC+Driver+18+for+SQL+Server
```

> لو لا تحتاج SQL Server محليًا، علّق هذا السطر وارجع للافتراضي:
> `DATABASE_URL=sqlite+aiosqlite:///./ppe_detection.db`

### الخطوة 3: ولّد `JWT_SECRET` قوي وثبّته

```powershell
python scripts/gen_jwt_secret.py
```

انسخ القيمة المطبوعة وضعها في `.env`:

```env
JWT_SECRET=<القيمة-المطبوعة>
```

القيمة القوية طولها ~64 حرف عشوائي (48 بايت). أي قيمة أقصر من 32 بايت ستوقف التشغيل برسالة واضحة.

### الخطوة 4 (مستحسن): ثبّت باسورد الـ admin المحلي

بدل الباسورد العشوائية المتغيرة مع كل reload، ضع واحدة قوية في `.env`:

```env
BOOTSTRAP_USERNAME=admin
BOOTSTRAP_PASSWORD=<باسورد-قوية-مؤقتة>
```

ستُطلب منك تغييرها إجباريًا عند أول تسجيل دخول.

### الخطوة 5: شغّل السيرفر بالأمر الموصى به

```powershell
python -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

- `--reload-dir app` يراقب كود التطبيق فقط (أسرع، وبدون reload عشوائي من `.venv` أو الفريمات).
- ملاحظة: تعديل `.env` **لا** يعيد التشغيل تلقائيًا — أوقف (`CTRL+C`) وشغّل من جديد بعد أي تعديل فيه.

---

## 4. كيف تتأكد إن كل حاجة سليمة؟ ✅

1. **اللوج**: لازم تشوف بالترتيب `Database migrations applied` ثم `Camera manager started — API is ready`
   ثم من Uvicorn: `Application startup complete`.
2. **الصحة**: افتح `http://127.0.0.1:8000/api/v1/health` — لازم يرجع `{"status":"ok"}`.
3. **التوثيق**: افتح `http://127.0.0.1:8000/docs` (متاح في `dev` فقط).
4. **لا تحذيرات**: اختفاء `InsecureKeyLengthWarning` تمامًا بعد تثبيت `JWT_SECRET` قوي.
5. **الدخول**: سجّل دخول من الداشبورد (`npm run dev` في `frontend/` ثم `http://localhost:5173`)
   وغيّر الباسورد المؤقتة عند أول دخول.

---

## 5. رسائل الخطأ الجديدة ومعناها

| الرسالة | المعنى والحل |
|---|---|
| `JWT_SECRET is too weak for HS256: it is 22 bytes long...` | نفّذ الخطوة 3 أعلاه |
| `Database startup failed for mssql...` + `pip install -r requirements/mssql.txt` | نفّذ الخطوة 2 أعلاه |
| `...ODBC driver...` / `Data source name not found` | ثبّت ODBC Driver 18 وتأكد من اسم السيرفر والبورت |
| `Detection model weights not found ... Checked: ...` | ملف `.pt` ناقص — ضعه في `Model/` أو صحّح المسار في `.env` |
| `The 'ultralytics' package is not installed...` | نفّذ الخطوة 1 (تثبيت الاعتماديات) |
| `Frontend bundle not found — API-only mode` | **ليست مشكلة**: معناها أن الـ API شغال بدون واجهة مبنية — استخدم `npm run dev` للدشبورد |

---

## 6. وصفة `.env` مستقر للتطوير المحلي

```env
APP_ENV=dev
DATABASE_URL=sqlite+aiosqlite:///./ppe_detection.db
JWT_SECRET=<من scripts/gen_jwt_secret.py>
BOOTSTRAP_USERNAME=admin
BOOTSTRAP_PASSWORD=<باسورد-قوية-مؤقتة-تتغير-عند-أول-دخول>
ALLOWED_RTSP_PREFIXES=
ALLOWED_VIDEO_DIR=./videos
```

- `ALLOWED_RTSP_PREFIXES` فارغة = كل مصادر الشبكة مقفولة (الوضع الآمن الافتراضي).
- لا تستخدم قيم هذا الملف في الإنتاج — الإنتاج له `python scripts/setup_onprem.py`.
