import cv2
import numpy as np
import requests

# Thresholds
thres = 0.45  # Confidence threshold
nms_threshold = 0.2  # Non-Maximum Suppression threshold

# Open webcam
cap = cv2.VideoCapture(0)
# Optional: Set resolution and brightness
# cap.set(3, 1280)  # Width
# cap.set(4, 720)   # Height
# cap.set(10, 150)  # Brightness

# Load class names
classNames = []
classFile = 'coco.names'  # Make sure this file exists in the same directory
with open(classFile, 'rt') as f:
    classNames = f.read().rstrip('\n').split('\n')

# Load model config and weights
configPath = 'ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt'
weightsPath = 'frozen_inference_graph.pb'

net = cv2.dnn_DetectionModel(weightsPath, configPath)
net.setInputSize(320, 320)
net.setInputScale(1.0 / 127.5)
net.setInputMean((127.5, 127.5, 127.5))
net.setInputSwapRB(True)

# Main loop
while True:
    success, img = cap.read()
    if not success:
        break

    classIds, confs, bbox = net.detect(img, confThreshold=thres)
    bbox = list(bbox)
    confs = list(np.array(confs).reshape(1, -1)[0])
    confs = list(map(float, confs))

    indices = cv2.dnn.NMSBoxes(bbox, confs, thres, nms_threshold)

    count = 0

    for i in indices:
        i = i[0] if isinstance(i, (list, np.ndarray)) else i
        classId = classIds[i][0] if isinstance(classIds[i], (list, np.ndarray)) else classIds[i]
        label = classNames[classId - 1].lower()

        if label == 'bottle':
            box = bbox[i]
            x, y, w, h = box[0], box[1], box[2], box[3]
            cv2.rectangle(img, (x, y), (x + w, y + h), color=(0, 255, 0), thickness=2)

            # Send HTTP request
            try:
                if count == 0:
                    response = requests.get(url="http://127.0.0.1:5000/offload")
                    print(f"Request sent. Status code: {response.status_code}")
                    i+=1
            except Exception as e:
                print(f"Request failed: {e}")

            cv2.putText(img, label, (x + 10, y + 30),
                        cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Output", img)

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
