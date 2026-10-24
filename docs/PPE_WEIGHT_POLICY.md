# سياسة الوزن المعتمد — Model/ppe.pt

## الوزن الوحيد

| البند | القيمة |
| --- | --- |
| اسم الملف المقبول | `ppe.pt` فقط |
| المسار الافتراضي | `Model/ppe.pt` |
| الثابت البرمجي | `app/core/model_policy.py` → `MODEL_FILENAME = "ppe.pt"` |
| البصمة الموصى بها | `PPE_MODEL_SHA256=15c758c669eeb557d9439bd18c5a3929680238122a95286210ca69e11af8218a` |
| محمّل النموذج | `app/core/detector.py` (منشئ `YOLO` واحد) |
| بوابة ما قبل التشغيل | `python -m app.model_check [--smoke]` |

## الرفض الصريح للأوزان unified

أي مسار أو اسم يحتوي `unified` أو `ppe_unified_best` يُرفض في:

- `Settings` عند قراءة `PPE_MODEL_PATH` (أي أن الخادم لا يبدأ).
- `app/core/model_policy.validate_model_path` قبل وبعد `resolve()` (بما في ذلك symlink يشير إلى وزن unified).
- `app/model_check` عند الفحص المسبق.

الرسالة الموحّدة:

```text
Only approved weight Model/ppe.pt is allowed; unified weights are rejected.
```

كما يُرفض أي ملف لا يكون اسمه `ppe.pt` بعد `resolve()`، وأي مسار يحتوي `://`، وأي مسار فارغ.

## التحقق من SHA-256

يُتحقق من البصمة فقط إن كانت `PPE_MODEL_SHA256` مضبوطة (64 حرفًا hex). عدم التطابق يوقف الاستدلال قبل تحميل ultralytics. البصمة ثابتة معلنة في `APPROVED_MODEL_SHA256` داخل `app/core/model_policy.py`.

## الفئات المتوقعة من ppe.pt (13)

```text
Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest, Mask, NO-Mask,
Person, Gloves, NO-Gloves, Safety Boots, NO-Safety Boots, Goggles, NO-Goggles
```

- `Mask` و`NO-Mask` غير صناعيتين: تُتجاهلان في العرض والقواعد دون إسقاط التشغيل، ولا تظهران كفئات منتج أو عدادات.
- `NO-Safety Boots` و`Safety Boots` تُطبّعان إلى `NO-Boot` و`Safety Boots` في المفردات القياسية.
- لا تُطلب فئات `Ladder` أو `Cone` أو `Excavator`، وتُتجاهل إن ظهرت.
- الحد الأدنى للتحميل: `Person` و`Hardhat` و`NO-Hardhat` و`Safety Vest`.

## طبقة القرار الإلزامية

`resolve_ppe_conflicts` في `app/core/postprocess.py` تعمل قبل الرسم (`app/core/frame_annotator.py`) وقبل `violation_checker.py` وقبل عدادات الكاميرا وJSON:

- لا يظهر `Hardhat` و`NO-Hardhat` معًا على الشخص نفسه؛ الموجب يفوز عند التعادل أو الفرق `< 0.15` لصالح السالب.
- عتبة الدليل السالب `DETECTION_NEGATIVE_CONFIDENCE = 0.60` كحد أدنى (لا يمكن ضبطها أقل من ذلك)، وتُطبّق للعرض والتنبيه معًا؛ الموجب يظل يظهر من `DETECTION_CONFIDENCE` (0.50 افتراضيًا).
