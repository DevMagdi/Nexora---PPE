# قائمة ملفات تحديث المصادر وMANTIK

أساس PR: `dba1570bf9a9d54533e3cab71d7b34460d6aec36`. الفرع: `arena/161684fc-nexora-ppe`.

**77 ملفًا: 24 مضاف، 53 معدل، 0 محذوف.** منطق محمل الاستدلال مطابق لآخر main؛ تنسيق PPE واختبارات التوافق فقط إضافية على قائمة تطوير المصادر والواجهة.

A = إضافة، M = تعديل. تشمل القائمة ملفات المصدر والاختبارات والتوثيق وست لقطات مراجعة؛ لا تشمل node_modules أو البيئات أو تقارير الاختبار الآلية المتجاهلة أو أوزانًا أو بيانات كبيرة.

| الحالة | الملف | سبب التغيير |
| --- | --- | --- |
| M | `.env.example` | توثيق مفاتيح HTTP/USB والمهل والمحاولات وحدود HLS، وإبقاء HTTP/USB مغلقين افتراضيًا. |
| M | `README.md` | مصفوفة الأنواع والدعم الفعلي والأمان والهوية الهادئة والحدود وروابط تقارير هذا التحديث. |
| M | `app/api/routes/cameras.py` | إنشاء/تحديث مصدر مضبوط النوع والمصادقة، تنقيح الأسرار، وإرجاع حالة وخطأ اتصال آمنين. |
| M | `app/api/routes/meta.py` | إعلان الأنواع والقدرات المفعلة وUSB dev-only وONVIF metadata-only دون ادعاء discovery. |
| M | `app/camera/file_source.py` | وسم الملف بأنه غير قابل لإعادة الاتصال التلقائية، مع إبقاء القراءة الأصلية مرة واحدة. |
| A | `app/camera/hls_decoder.py` | طفل PyAV/FFmpeg ببروتوكولات شبكة معطلة وخرج محدود وPTS؛ عزل تعليق/انهيار الفك عن API. |
| A | `app/camera/hls_media.py` | فحص TS/BMFF وAES-128 لمنع القوائم المتنكرة والمراجع الخارجية للملفات قبل الفك الأصلي. |
| A | `app/camera/hls_source.py` | جلب وفحص موارد HLS وإعادة كتابة محلية ذرية، مخزن محدود، تحديث حي وPTS pacing وعملية فك مستقلة قابلة للإيقاف. |
| A | `app/camera/http_client.py` | HTTP محكوم بمهل وحدود، DNS pinning وHost/SNI، منع التحويلات وتسرب المصادقة وتنقيح سجلات URL. |
| M | `app/camera/manager.py` | مصنع المحولات الستة، حالات اتصال ومحاولات محدودة ومسح البيانات القديمة وتحرير الموارد والخطأ المحفوظ، دون تغيير كاشف PPE. |
| A | `app/camera/mjpeg_source.py` | قراءة multipart MJPEG فعلية وفحص JPEG والدقة وحدود الحجم والمهل والتنظيف. |
| M | `app/camera/source_security.py` | مطابقة النوع والبروتوكول، قوائم HTTP مستقلة، فحص العناوين والمسارات، وضبط الملف وUSB وONVIF والمصادقة. |
| A | `app/camera/types.py` | تعريف موحد مغلق لأنواع المصادر الستة. |
| A | `app/camera/usb_source.py` | التقاط USB dev-only داخل عملية منفصلة مع مهل وإنهاء السائق المعلق. |
| M | `app/core/config.py` | قوائم ومهل وحدود المصادر الجديدة، والتحقق من منع USB/loopback خارج dev ومن إعداد إنتاج محكوم. |
| M | `app/db/models.py` | أربعة أعمدة إضافية للمصدر والمصادقة وتعريف ONVIF والخطأ الآمن. |
| M | `app/schemas/camera.py` | عقد الأنواع الستة وحقول مناسبة للنوع وأسرار كتابة فقط وحالة اتصال واضحة. |
| M | `docker-compose.yml` | قائمة HTTP اختيارية وHTTP-only دون RTSP صوري، وتعطيل USB/loopback صراحةً في الإنتاج. |
| M | `docs/CHANGE_MANIFEST.md` | تحديد القائمة السابقة كسجل تاريخي وربط قائمة دلتا التحديث الحالي، دون إعادة كتابة تاريخ PR16. |
| M | `docs/INDUSTRIAL_GUIDE_AR.md` | دليل إعداد الأنواع والمنافذ والمصادقة والسياسة والمهل وقيود HLS وONVIF والوسطاء والترحيل. |
| M | `docs/LOCAL_RUN_TROUBLESHOOTING_AR.md` | تشخيص رفض HTTP/تحويلاته وHLS/USB واعتماد PyAV وحدود ONVIF. |
| M | `docs/ON_PREM_SECURITY_AR.md` | حدود الشبكة والأسرار وHTTP-only والتعطيل الإنتاجي والترحيل الإضافي. |
| A | `docs/SOURCE_AND_THEME_UPDATE.md` | تقرير التنفيذ والاختبارات واللقطات والحدود التي لم تُختبر ميدانيًا. |
| A | `docs/SOURCE_THEME_CHANGE_MANIFEST.md` | هذه القائمة الكاملة لدلتا الفرع مع سبب كل ملف. |
| M | `docs/VALIDATION_REPORT.md` | تحديد النتائج السابقة كتاريخية وربط تقرير التحديث الحالي. |
| A | `docs/review/mantik-dashboard-desktop.png` | لقطة واجهة فعلية من اختبارات المتصفح، ببيانات fixtures صريحة وليست بيانات موقع/نموذج حي. |
| A | `docs/review/mantik-dashboard-mobile.png` | لقطة واجهة فعلية من اختبارات المتصفح، ببيانات fixtures صريحة وليست بيانات موقع/نموذج حي. |
| A | `docs/review/mantik-login-desktop.png` | لقطة واجهة فعلية من اختبارات المتصفح، ببيانات fixtures صريحة وليست بيانات موقع/نموذج حي. |
| A | `docs/review/mantik-login-mobile.png` | لقطة واجهة فعلية من اختبارات المتصفح، ببيانات fixtures صريحة وليست بيانات موقع/نموذج حي. |
| A | `docs/review/mantik-source-desktop.png` | لقطة واجهة فعلية من اختبارات المتصفح، ببيانات fixtures صريحة وليست بيانات موقع/نموذج حي. |
| A | `docs/review/mantik-source-mobile.png` | لقطة واجهة فعلية من اختبارات المتصفح، ببيانات fixtures صريحة وليست بيانات موقع/نموذج حي. |
| M | `frontend/src/App.tsx` | تمرير قدرات المصدر الفعلية من meta إلى نموذج إدارة الكاميرات. |
| M | `frontend/src/auth/AuthGate.tsx` | أيقونات ونصوص ثانوية أهدأ وإزالة الدوران الزخرفي، مع بقاء الدخول وحماية الجلسة. |
| M | `frontend/src/auth/PasswordChangeScreen.tsx` | تهدئة الأيقونة الثانوية والحالة المنتظرة دون تغيير فرض تبديل كلمة المرور. |
| M | `frontend/src/cameras/CameraForm.tsx` | نوع المصدر أولًا، حقول ديناميكية عربية ومصادقة مقنّعة بلا تعبئة محفوظة وتحذيرات USB/ONVIF. |
| M | `frontend/src/cameras/CamerasPage.tsx` | تسميات الأنواع والحالات والخطأ الصريح وإيقاف المحاولة وإرشاد وتشغيل محكوم وتنقيح العرض. |
| A | `frontend/src/cameras/sources.test.ts` | اختبارات وحدات للأنواع الستة ومطابقة URI والملفات ومنع المصادقة المضمنة في النموذج. |
| A | `frontend/src/cameras/sources.ts` | بيانات الاختيار والتسميات والإرشاد والتحقق العميل من النوع/URI وحالة الاتصال. |
| M | `frontend/src/components/Feedback.tsx` | إزالة الدوران الزخرفي من التغذية الراجعة مع حفظ النصوص والحالات الدلالية. |
| M | `frontend/src/components/RulePicker.tsx` | تخفيف حد الاختيار الذهبي وتوسيع مساحة خيارات القواعد دون تغيير القواعد. |
| M | `frontend/src/components/ui/button.tsx` | أزرار أكثر راحة، زوايا موحدة، أساسي ذهبي ممتلئ وhover لطيف180ms. |
| M | `frontend/src/components/ui/dialog.tsx` | حوار هادئ بظل ومسافة موحدين، دون دخول/خروج/تكبير متحرك، مع حفظ الإتاحة. |
| M | `frontend/src/dashboard/LivePage.tsx` | إظهار الفشل/الاكتمال/المحاولة وإيقاف المحاولة وإرشاد الحالة بدل وصف كل مصدر بأنه متوقف. |
| M | `frontend/src/dashboard/Overview.tsx` | مسافات أوسع ومتسقة لشبكات اللوحة دون تغيير منطق SQL/الرسم أو بيانات الإحصاءات. |
| M | `frontend/src/dashboard/SitesPage.tsx` | مسافات وبطاقات هادئة وحالات انتظار بلا دوران، مع حفظ وظائف المواقع. |
| M | `frontend/src/dashboard/UploadsPage.tsx` | حدود/أيقونات محايدة وزوايا ومسافات موحدة وحالات انتظار هادئة، دون تغيير الرفع والاستدلال. |
| M | `frontend/src/dashboard/UsersPage.tsx` | تقليل الذهبي الثانوي وحالات انتظار بلا دوران، مع حفظ الأدوار وعرض الكلمات المؤقتة المشروع. |
| M | `frontend/src/hooks/useLiveCamera.ts` | مسح العدادات عند رسالة انقطاع/اكتمال دون اختلاق أعداد، مع حفظ آلية الجلسة والبث. |
| M | `frontend/src/index.css` | التخطيط والمسافات والفواصل والحقول والبطاقات والخلفية الطويلة وRTL والمؤشر النشط وإزالة الحركة الزخرفية. |
| M | `frontend/src/layout/Sidebar.tsx` | نصوص ثانوية محايدة وأهدأ مع الاحتفاظ بالملاحة وRTL. |
| M | `frontend/src/layout/Topbar.tsx` | تهدئة الذهبي الثانوي وإزالة دوران زخرفي دون تغيير الوظائف. |
| M | `frontend/src/lib/formatters.ts` | إزالة الأخضر من لون فئة الرسم التي لا تدل على نجاح؛ لا تغيير لحساب الإحصاءات. |
| M | `frontend/src/lib/utils.ts` | ترجمة أخطاء سياسة المصدر والمنفذ إلى إرشاد عربي مفهوم. |
| M | `frontend/src/theme/mantik.css` | المصدر الوحيد للألوان؛ حفظ القيم التسع وتخفيف الحدود والظلال والتدرج والفواصل وزوايا1.1rem. |
| M | `frontend/src/types/index.ts` | عقد TypeScript للأنواع والقدرات والمصادقة للكتابة فقط والحالات الجديدة. |
| M | `frontend/src/violations/EventTable.tsx` | إزالة دوران انتظار المعالجة فقط؛ لا تغيير للأحداث أو الدليل. |
| M | `frontend/src/violations/ViolationsPage.tsx` | مسافات هادئة وإزالة دوران زخرفي مع حفظ الفلاتر والتصدير. |
| A | `frontend/tests/e2e/camera-sources.spec.ts` | سيناريوهات الأنواع والمصادقة وUSB والفشل والنموذج والإتاحة وقياسات نعومة الهوية على الهاتف/سطح المكتب. |
| M | `frontend/tests/e2e/console.spec.ts` | تحديث تسميات النموذج وإضافة لقطات الدخول مع حفظ السيناريوهات السابقة وفحوص axe/RTL. |
| M | `frontend/tests/e2e/fixtures.ts` | تحديث عقد API الاختباري للأنواع والقدرات والأخطاء والأسرار للكتابة فقط، دون استيراده في الإنتاج. |
| A | `migrations/versions/20261024_camera_source_types.py` | ترحيل إضافي غير حاذف وتصحيح صفوف RTSPS القديمة مع الحفاظ على البيانات. |
| M | `requirements/runtime.txt` | PyAV18.1+ (قبل19) كمفكك FFmpeg معزول لـHLS، لا نموذج استدلال إضافي. |
| M | `requirements/test.txt` | imageio-ffmpeg لتوليد عينات الفيديو للاختبارات فقط، وليس لفك HLS التشغيلي. |
| M | `scripts/setup_onprem.py` | دعم --http-prefix وتثبيت HTTP-only محكوم، وإجبار تعطيل USB/loopback في إعداد الإنتاج. |
| M | `tests/conftest.py` | استكمال عقد mock مدير الكاميرات بحالة اتصال وخطأ آمنين. |
| A | `tests/integration/test_camera_source_types_api.py` | عقد الأنواع الستة والأسرار والمنفذ والسياسة وONVIF وتبديل النوع والفشل المحفوظ وقدرات الإنتاج. |
| A | `tests/integration/test_http_camera_sources.py` | خادم HTTP محلي محكوم وعينات TS/fMP4/AES/MJPEG حقيقية وفحص المصادقة وPTS وEOF والتحديث والإيقاف. |
| M | `tests/unit/test_camera_manager_liveness.py` | تحديث توقع نص غياب أول إطار إلى الرسالة العربية الحالية مع حفظ اختبار التحرير. |
| M | `tests/unit/test_deployment_contract.py` | إثبات إعداد HTTP-only صالح وتعطيل USB/loopback دون RTSP صوري. |
| A | `tests/unit/test_hls_confinement.py` | منع تجاوز السياسة والمفاتيح/الخرائط الملتبسة والقوائم المتنكرة وملفات MP4 الخارجية وحدود HTTP. |
| A | `tests/unit/test_http_source_security.py` | تطابق النوع والURI وسياسة العنوان/DNS والأسرار والأصول والتحويلات وأعلام dev والmetadata. |
| M | `tests/unit/test_industrial_scope_contract.py` | القيم التسع وحد0.12 وزوايا1.1 وإزالة الحركة ومصدر ألوان وحيد، مع حفظ قيد نموذج واحد. |
| M | `tests/unit/test_migration_runtime.py` | تحديث توقع رأس Alembic إلى الترحيل الإضافي الجديد. |
| M | `tests/unit/test_security_migration.py` | تحديث الرأس واختبار ترقية إضافية تحافظ على الكاميرات والقواعد والمواقع والأحداث والعلاقات. |
| A | `tests/unit/test_source_recovery_and_usb.py` | اختبارات حد المحاولات ومسح البيانات القديمة والتعافي وعزل سائق USB اصطناعي معلق. |

تفاصيل التنفيذ والتحقق والقيود في [تقرير التحديث](SOURCE_AND_THEME_UPDATE.md). حالة Pull Request وفحوص CI والدمج النهائي مسجلة في GitHub.

| M | `app/core/ppe.py` | تنسيق Ruff فقط لتصحيح فشل CI الموجود على main؛ ثُبت تطابق AST دون تغيير منطق تحديث النموذج. |
| M | `tests/unit/test_model_files.py` | مطابقة سياسة main الحالية مع اختبار الحد الأدنى وكل فئة مطلوبة واستبعاد IDs المتجاهلة والتكرار وعدم اختلاق المخالفات الغائبة. |
