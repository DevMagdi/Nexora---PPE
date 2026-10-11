from ultralytics import YOLO
import cv2

# -------------------------
# Config (زي .env / settings)
# -------------------------
MODEL_PATH = "Model/bestMedicalModel2.pt"
IMAGE_PATH = "test.jpg"

MEDICAL_DETECTION_CONFIDENCE = 0.05  # زي MEDICAL_DETECTION_CONFIDENCE
MEDICAL_DEFAULT_CLASS_CONF = 0.25    # زي MEDICAL_DEFAULT_CLASS_CONF

# زي MEDICAL_CLASS_CONF_THRESHOLDS (بالـ class_id)
# مهم: شدّد على positives (gloves/mask) لتقليل FP
CLASS_CONF = {
    2: 0.70,  # hand gloves
    5: 0.70,  # mask
    7: 0.15,  # no hand gloves
    8: 0.20,  # no head cap
    9: 0.30,  # no mask
}

# لو عايز تطبع بس الكلاسات دي
FOCUS_NAMES = {"hand gloves", "no hand gloves", "mask", "no mask", "head cap", "no head cap", "goggle", "no goggle"}

# -------------------------
# Inference
# -------------------------
m = YOLO(MODEL_PATH)
img = cv2.imread(IMAGE_PATH)

# فلتر YOLO الأول
r = m.predict(img, conf=MEDICAL_DETECTION_CONFIDENCE, verbose=False)[0]

names = m.names

# نتائج قبل فلتر الباك (raw)
raw = []
for b in (r.boxes or []):
    cls_id = int(b.cls[0])
    conf = float(b.conf[0])
    raw.append((names.get(cls_id, str(cls_id)), cls_id, conf))

raw_sorted = sorted(raw, key=lambda x: -x[2])

print("\n=== RAW (after YOLO conf filter only) top 30 ===")
for item in raw_sorted[:30]:
    if item[0] in FOCUS_NAMES:
        print(item)

# فلتر الباك الثاني (default/per-class thresholds)
filtered = []
for name, cls_id, conf in raw_sorted:
    thr = CLASS_CONF.get(cls_id, MEDICAL_DEFAULT_CLASS_CONF)
    if conf >= thr:
        filtered.append((name, cls_id, conf, thr))

print("\n=== FILTERED (like backend thresholds) ===")
for item in filtered:
    name, cls_id, conf, thr = item
    if name in FOCUS_NAMES:
        print(f"{name:14s} id={cls_id:2d} conf={conf:.3f} (thr={thr:.2f})")

print("\n=== FILTERED top 30 (all classes) ===")
for name, cls_id, conf, thr in filtered[:30]:
    print(f"{name:14s} id={cls_id:2d} conf={conf:.3f} (thr={thr:.2f})")