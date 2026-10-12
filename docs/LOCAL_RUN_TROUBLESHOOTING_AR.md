# دليل استكشاف التشغيل المحلي (Local Run Troubleshooting)

> هذا الدليل لتشخيص تشغيل `python -m uvicorn app.main:app --reload` على Windows/Linux،
> وبالذات توقف startup عند Alembic، بث الكاميرا، وتحذير مفتاح JWT الضعيف.

---

## 1. تحليل اللوج المرسل — وصل لفين فعلًا؟

الجزء الذي أرسلته:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process ... using WatchFiles
INFO:     Started server process ...
INFO:     Waiting for application startup.
2026-10-12 15:44:49 | INFO     | app.main | Starting Nexora PPE API (env=dev)
2026-10-12 15:44:49 | INFO     | app.main | Database backend: SQL Server (aioodbc)
2026-10-12 15:44:49 | INFO     | app.main | Applying database migrations...
INFO  [alembic.runtime.migration] Context impl MSSQLImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

**المؤكد من المقتطف:** Uvicorn بدأ، ومرحلة migrations بدأت، وAlembic تعرّف على SQL Server. ظهور `Context impl MSSQLImpl` يعني أن اتصال Alembic المتزامن اتفتح؛ لكنه **لا** يعني أن الـ migrations خلصت أو أن الـ API جاهز. و`Will assume transactional DDL` رسالة عن أسلوب المعاملة فقط.

لا يظهر `Application startup complete` في المقتطف، لذلك لا نقدر نؤكد أن السيرفر كان جاهزًا وقت أخذ اللوج. لكن غياب `Database migrations applied` وباقي رسائل `app.main` **لوحده لا يثبت أن التطبيق علق**: كان إعداد Alembic يعيد ضبط مستوى root logger إلى `WARNING`، فيخفي رسائل `INFO` التي تأتي بعد `Applying database migrations...` حتى لو التطبيق أكمل. اتصلح ده الآن بالحفاظ على مستوى اللوج والـ loggers بعد Alembic. بعد الإصلاح، لو انتهى اللوج عند سطر معيّن، تقدر تحدد مرحلة الانتظار فعلًا.

بعد إضافة سجلات تشخيصية وحدّ لانتظار اتصال/lock قاعدة البيانات، التسلسل المتوقع يكون قريبًا من:

```text
Applying database migrations...
INFO [alembic.runtime.migration] Opening database connection for Alembic migrations...
INFO [alembic.runtime.migration] Alembic database connection established (dialect=mssql)
INFO [alembic.runtime.migration] SQL Server migration lock wait limited to 15000 ms
INFO [alembic.runtime.migration] Checking current schema revision and applying pending migrations...
INFO [alembic.runtime.migration] Context impl MSSQLImpl.
INFO [alembic.runtime.migration] Will assume transactional DDL.
INFO [alembic.runtime.migration] Running upgrade ...
INFO [alembic.runtime.migration] Alembic migration run completed
Database migrations applied
...
Camera manager started — API is ready
INFO:     Application startup complete.
```

لو آخر سطر عندك ما زال `Will assume transactional DDL`، انتظر حدّ الـ lock المُعدّ (15 ثانية افتراضيًا) ثم راجع رسالة الخطأ الجديدة. إذا ظهر `lock timeout`، أوقف أي نسخة API/Alembic أخرى تستخدم نفس قاعدة SQL Server وافحص المعاملات المفتوحة. **لا تغيّر `DATABASE_URL` إلى SQLite عشوائيًا**؛ ده ممكن يفتح قاعدة مختلفة ويخلي بيانات SQL Server تبدو كأنها اختفت.

### تحذير JWT حالة منفصلة

`InsecureKeyLengthWarning` لا يظهر في المقتطف الحالي. لو ظهر في لوج آخر عند تسجيل الدخول، فده يعني أن `JWT_SECRET` أقصر من 32 بايت؛ لكنه لا يفسّر التوقف عند Alembic. الإعدادات الحالية ترفض المفتاح الضعيف برسالة واضحة قبل قبول الطلب.

---

## 2. المشاكل التي يغطيها الإصلاح

### المشكلة 1: رسائل التطبيق اختفت بعد بدء Alembic

- `fileConfig()` في migrations كان يغيّر root logger إلى `WARNING` ويعطّل بعض `app.*` loggers؛ رسائل `INFO` مثل `Database migrations applied` و`Loading detection models` كانت تختفي بعد سطر Alembic. ده يفسّر “مفيش لوج في الباك” حتى لو التطبيق كان مستمرًا.
- تم الحفاظ على الـ loggers ومستوى اللوج الأصلي، وإضافة سجلات لكل مرحلة من اتصال Alembic حتى اكتمال migration.
- لو انتهى اللوج فعلًا عند خطوة في SQL Server، أُضيفت مهلة اتصال و`DB_MIGRATION_LOCK_TIMEOUT_MS` (افتراضيًا 15000ms) على SQL Server؛ بعد انتهاء المهلة يفشل startup برسالة قابلة للتشخيص بدل انتظار lock بلا نهاية.
- لو ظهر lock timeout، أوقف أي نسخة API/Alembic أخرى وافحص معاملات SQL Server المفتوحة قبل إعادة المحاولة.

### المشكلة 2: بث الكاميرا كان يُعتبر شغالًا لمجرد أن OpenCV فتح المصدر

- فتح `VideoCapture` لا يضمن أن `read()` يرجّع frame. وكان اللوب يتجاهل `None` بصمت، فيبقى المصدر “شغالًا” لكن بدون فيديو أو إحصائيات.
- الآن تشغيل الكاميرا ينتظر أول frame مُعالج، ويُرجع سببًا مفهومًا إن لم يصل خلال المهلة. فشل قراءة الإطارات يُسجّل بتحذير محدود التكرار، والكاميرا القديمة التي لا يصل منها frame جديد لا تُعرض كأنها بث حي.

### المشكلة 3: اتصال WebSocket قد يُرفض رغم أن صفحة الداشبورد من نفس السيرفر

- كان التحقق يقارن نص `Origin` مع `Host` حرفيًا، فأي اختلاف بين الاسمين المحليين (صفحة على `http://localhost:8000` والاتصال على `ws://127.0.0.1:8000` أو العكس) كان يرفض الاتصال بـ `403 untrusted origin` رغم أنه نفس الجهاز.
- الآن المقارنة على مستوى **الـ hostname**: يُسمح بالـ origin المدرج صراحةً في `CORS_ORIGINS`، أو أي origin اسمه مطابق للـ Host، أو أحد أسماء loopback المعتادة (`localhost` / `127.0.0.1` / `::1`) مقابل بعضها. كل الدومينات الخارجية وأي محاولة انتحال (مثل `localhost.attacker.invalid`) تظل مرفوضة، والرفض الآن يسجّل قيمة الـ origin والـ host في اللوج لتشخيص أسرع.
- إذا ظهر الرفض رغم ذلك فالمشكلة غالبًا **bundle قديم في كاش المتصفح**: أعِد بناء الواجهة (`npm run build`) — و`index.html` الآن يُخدم بـ `Cache-Control: no-store` لمنع هذه الحالة نهائيًا.

### المشكلة 4: JWT وSQL Server والتطوير المحلي

- المفتاح `JWT_SECRET` القصير (أقل من 32 بايت) يُرفض برسالة واضحة؛ هذا **موضوع منفصل** عن تعليق Alembic.
- `requirements/mssql.txt` يثبت `aioodbc/pyodbc`، لكن يلزم أيضًا تثبيت ODBC Driver من Microsoft على Windows.
- شغّل Uvicorn مع `--reload-dir app` لتقليل مراقبة ملفات البيئة والإطارات.
- أسرار التطوير العشوائية تتغير مع كل reload؛ ضع `JWT_SECRET` و`BOOTSTRAP_PASSWORD` ثابتين في `.env` المحلي.

### مهم: معنى “كاميرا الويب مفتوحة”

مصدر `webcam` يقرأ الكاميرا عبر OpenCV **داخل عملية Python التي تشغل الـ backend**، وليس عبر صلاحية الكاميرا في متصفح المستخدم. لذلك:

- لازم تختار index صحيحًا (`0` غالبًا) على الجهاز الذي يعمل عليه الـ backend، وتسمح لـ Python في Windows Camera Privacy.
- اقفل تطبيقات أخرى قد تكون ماسكة نفس الكاميرا.
- إذا كان الـ backend داخل Docker، فالكاميرا المتصلة بجهازك لا تظهر للحاوية تلقائيًا؛ `docker-compose.dev.yml` لا يمرر جهاز webcam. شغّل backend على الجهاز المضيف أو استخدم كاميرا شبكة/مصدر فيديو مسموح.
- ظهور `مباشر` مرتبط بقناة telemetry عبر WebSocket؛ الفيديو نفسه يصل عبر MJPEG. أصبحت أسباب رفض كل قناة ظاهرة في لوج backend.

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

> لا تغيّر نوع قاعدة البيانات لمجرد تجربة التشغيل إذا كانت بياناتك في SQL Server؛ SQLite قاعدة منفصلة. استخدم SQLite فقط لو تقصد فعلًا قاعدة تطوير محلية جديدة.

المهلة الافتراضية للاتصال 15 ثانية، وانتظار lock أثناء ترحيل SQL Server 15 ثانية. يمكن تعديلهما في `.env` بعد فحص سبب الانتظار:

```env
DB_MIGRATION_CONNECT_TIMEOUT_SECONDS=15
DB_MIGRATION_LOCK_TIMEOUT_MS=15000
```

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
6. **تشغيل webcam**: بعد الضغط على تشغيل، راقب backend بحثًا عن `Opening camera source` ثم `Webcam 0 opened` و`first processed frame ready`. غياب أول سطر يعني أن الطلب لم يصل للـ backend؛ وظهور `no frame` يعني أن OpenCV فتح المصدر لكنه لا يقرأ إطارات.
7. **اتصال مباشر**: في أدوات المطور للمتصفح، افحص `/api/v1/ws/<camera_id>`؛ يجب أن تكون WebSocket بحالة `101`. سيظهر سبب الرفض في backend من غير كشف بيانات الجلسة. طلب الفيديو هو `/api/v1/stream/<camera_id>` ويجب أن يكون `200` ونوعه `multipart/x-mixed-replace`.

---

## 5. رسائل الخطأ الجديدة ومعناها

| الرسالة | المعنى والحل |
|---|---|
| `JWT_SECRET is too weak for HS256: it is 22 bytes long...` | نفّذ الخطوة 3 أعلاه |
| `Database startup failed for mssql...` + `pip install -r requirements/mssql.txt` | نفّذ الخطوة 2 أعلاه |
| `...ODBC driver...` / `Data source name not found` | ثبّت ODBC Driver 18 وتأكد من اسم السيرفر والبورت |
| `lock timeout` أثناء Alembic | أوقف النسخ الأخرى التي تستخدم القاعدة، وافحص معاملات SQL Server المفتوحة، ثم أعد التشغيل |
| `no video frame arrived in time` | راجع index/خصوصية الكاميرا، اقفل التطبيقات الأخرى، وتأكد أن backend يعمل على الجهاز الذي لديه webcam أو أن الجهاز ممرر للحاوية |
| `Rejected WebSocket ... untrusted origin` | راجع الـ origin والـ host المكتوبين في اللوج؛ افتح الداشبورد من نفس الجهاز/الـ origin المضبوط في `CORS_ORIGINS`، وأعِد بناء الواجهة لو الـ bundle قديم |
| `Detection model weights not found ... Checked: ...` | ملف `.pt` ناقص — ضعه في `Model/` أو صحّح المسار في `.env` |
| `The 'ultralytics' package is not installed...` | نفّذ الخطوة 1 (تثبيت الاعتماديات) |
| `Frontend bundle not found — API-only mode` | **ليست مشكلة**: معناها أن الـ API شغال بدون واجهة مبنية — استخدم `npm run dev` للدشبورد |

---

## 6. وصفة `.env` مستقر للتطوير المحلي

```env
APP_ENV=dev
DATABASE_URL=sqlite+aiosqlite:///./ppe_detection.db
DB_MIGRATION_CONNECT_TIMEOUT_SECONDS=15
DB_MIGRATION_LOCK_TIMEOUT_MS=15000
JWT_SECRET=<من scripts/gen_jwt_secret.py>
BOOTSTRAP_USERNAME=admin
BOOTSTRAP_PASSWORD=<باسورد-قوية-مؤقتة-تتغير-عند-أول-دخول>
CAMERA_FIRST_FRAME_TIMEOUT_SECONDS=10.0
CAMERA_FRAME_STALE_SECONDS=15.0
ALLOWED_RTSP_PREFIXES=
ALLOWED_VIDEO_DIR=./videos
```

- `ALLOWED_RTSP_PREFIXES` فارغة = كل مصادر الشبكة مقفولة (الوضع الآمن الافتراضي).
- لا تستخدم قيم هذا الملف في الإنتاج — الإنتاج له `python scripts/setup_onprem.py`.
