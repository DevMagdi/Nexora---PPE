from ultralytics import YOLO

def main():
    model = YOLO('yolov8n.pt')

    model.train(
        data='dataset/data.yaml',
        epochs=30,
        imgsz=416,
        batch=8,
        workers=0,
        device='cpu',   # لو عندك NVIDIA خليه device=0
        name='nexora_ppe_v1',
        patience=15,
    )

if __name__ == '__main__':
    main()