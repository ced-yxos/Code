import cv2
import numpy as np

# Path to your ONNX model trained for fire detection
model_path = "best.onnx"

# Load the ONNX model
net = cv2.dnn.readNetFromONNX(model_path)

# Uncomment for GPU acceleration if OpenCV is built with CUDA
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

# Detection parameters
conf_threshold = 0.4
nms_threshold = 0.5
input_size = 640
label_name = "fire"

# Initialize webcam
cap = cv2.VideoCapture(0)

def preprocess(frame):
    blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (input_size, input_size), swapRB=True, crop=False)
    return blob

def postprocess(outputs, frame):
    frame_height, frame_width = frame.shape[:2]
    boxes = []
    confidences = []

    for detection in outputs[0]:
        scores = detection[5:]
        confidence = scores[0] * detection[4]  # Single class: fire
        if confidence > conf_threshold:
            cx, cy, w, h = detection[0:4]
            x = int((cx - w / 2) * frame_width / input_size)
            y = int((cy - h / 2) * frame_height / input_size)
            width = int(w * frame_width / input_size)
            height = int(h * frame_height / input_size)

            boxes.append([x, y, width, height])
            confidences.append(float(confidence))

    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)

    if len(indices) > 0:
        for i in indices:
            i = i[0] if isinstance(i, (list, tuple, np.ndarray)) else i
            x, y, w, h = boxes[i]
            label = f"{label_name}: {confidences[i]:.2f}"
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    blob = preprocess(frame)
    net.setInput(blob)
    outputs = net.forward()
    postprocess(outputs, frame)

    cv2.imshow("Fire Detection (YOLOv5-ONNX)", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
        break

cap.release()
cv2.destroyAllWindows()
