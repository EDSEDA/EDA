
import cv2
import numpy as np
import time
import json
import yaml
import dlib

from tensorflow.keras import applications
from tensorflow.keras.optimizers import SGD, Adam
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense

from keras.models import load_model
from datetime import datetime
from threading import Thread, Lock
from api.rabbit import mq_send
from api.config import EMOTION_LABELS, paths
from ultralytics import YOLO

from omegaconf import OmegaConf
from pathlib import Path

FRAME_RATE = 10
FACE_CLASSIFIER_MIN_NEIGHBORS=12
FACE_CLASSIFIER_MIN_SIZE=(56, 56)

mutex = Lock()
modelYolo = YOLO('../learning/data/yolov8n.pt')


def draw_label(image, point, label, font=cv2.FONT_HERSHEY_SIMPLEX,
               font_scale=0.8, thickness=1):
    size = cv2.getTextSize(label, font, font_scale, thickness)[0]
    x, y = point
    cv2.rectangle(image, (x, y - size[1]), (x + size[0], y), (255, 0, 0), cv2.FILLED)
    cv2.putText(image, label, point, font, font_scale, (255, 255, 255), thickness, lineType=cv2.LINE_AA)

def get_model(cfg):
    base_model = getattr(applications, cfg.model.model_name)(
        include_top=False,
        input_shape=(cfg.model.img_size, cfg.model.img_size, 3),
        pooling="avg"
    )
    features = base_model.output
    pred_sex = Dense(units=2, activation="softmax", name="pred_sex")(features)
    pred_age = Dense(units=101, activation="softmax", name="pred_age")(features)
    model = Model(inputs=base_model.input, outputs=[pred_sex, pred_age])
    return model

detector = dlib.get_frontal_face_detector()
model_name, img_size = Path("EfficientNetB3_224_weights.11-3.44.hdf5").stem.split("_")[:2]
img_size = int(img_size)
cfg = OmegaConf.from_dotlist([f"model.model_name={model_name}", f"model.img_size={img_size}"])
model = get_model(cfg)
model.load_weights("../learning/data/EfficientNetB3_224_weights.11-3.44.hdf5")

def try_detect_frame(worker_id: int, video_driver_path: str, cap: any, client_number: int):
    print("new detection")
    worker = dict.fromkeys(EMOTION_LABELS, 0)# для каждого айдишника в словаре задаем словарь эмоций
    worker["worker_id"] = worker_id

    prev = 0
    sex_avg = 0
    sex_count = 0
    age_avg = 0
    age_count = 0

    detected_track_id = -1

    while (True):
        time_elapsed = time.time() - prev
        is_frame, image_full = cap.read()

        if time_elapsed > 1. / FRAME_RATE:

            if is_frame == False:
                print("no frame")
                continue

            prev = time.time()

            # PERSON DETECTION
            results = modelYolo.track(image_full, persist=True)
            annotated_frame = results[0].plot()

            # if results[0].boxes.id == None and detected_track_id == -1:  # если объект никогда не появлялся на камере
            #     cv2.imshow("YOLOv8 Tracking", annotated_frame)
            #     continue
            #
            if results[0].boxes.id == None:  # если объект появлялся на камере и при этом пропал из списка обнаруженных
                continue

            if detected_track_id == -1:
                person_inds = [i for i, j in enumerate(results[0].boxes.cls.int().tolist()) if j == 0]  # получаем айдишники для объектов == человек в векторе айдишников
                if len(person_inds) == 0: # нормально, если первым кадром нейронка спутала человека с котом
                    cv2.imshow("YOLOv8 Tracking", annotated_frame)
                    continue

                person_ind = person_inds[0]  # пусть детектим первого попавшегося
                detected_track_id = results[0].boxes.id.int().tolist()[person_ind]  # достаем айдишник объекта и сохраняем его
                session_start_time = time.time()

            is_required_id_exist = False
            for person_ind, id in enumerate(results[0].boxes.id.int().tolist()):
                if detected_track_id == id:
                    is_required_id_exist = True
                    break

            if is_required_id_exist == False:
                print("no is_required_id_exist")
                print(results[0].boxes.id.int().tolist())
                print(detected_track_id)
                break

            xyxy = results[0].boxes.xyxy[person_ind].int().tolist()
            image_person = image_full[xyxy[1]:xyxy[3], xyxy[0]:xyxy[2]]

            label_person = "service time: {} sec, client number: {}".format(int(time.time() - session_start_time), client_number)
            draw_label(annotated_frame, (0, annotated_frame.shape[0]-10), label_person)
            cv2.imshow("YOLOv8 Tracking", annotated_frame)

            # HEAD DETECTION
            detected = detector(image_person, 1)
            faces = np.empty((1, img_size, img_size, 3))
            img_h, img_w, _ = np.shape(image_person)
            if len(detected) == 0:
                continue

            x1, y1, x2, y2, w, h = detected[0].left(), detected[0].top(), detected[0].right() + 1, detected[
                0].bottom() + 1, detected[0].width(), detected[0].height()
            xw1 = max(int(x1 - 0.4 * w), 0)
            yw1 = max(int(y1 - 0.4 * h), 0)
            xw2 = min(int(x2 + 0.4 * w), img_w - 1)
            yw2 = min(int(y2 + 0.4 * h), img_h - 1)
            image_head = image_person[yw1:yw2 + 1, xw1:xw2 + 1]
            faces[0] = cv2.resize(image_head, (img_size, img_size))

            # predict ages and sexs of the detected faces
            results = model.predict(faces)
            predicted_sexs = results[0]
            ages = np.arange(0, 101).reshape(101, 1)
            predicted_ages = results[1].dot(ages).flatten()

            # draw results
            predicted_age = predicted_ages[0]
            predicted_sex = predicted_sexs[0][0]
            age_avg = (age_avg * age_count + predicted_age) / (sex_count + 1)
            sex_avg = (sex_avg * sex_count + predicted_sex) / (sex_count + 1)
            age_count += 1
            sex_count += 1

            label_head = "ages: {}, sex: {}".format(int(age_avg), "Male" if sex_avg < 0.5 else "Female")
            draw_label(image_head, (0, yw2-yw1-10), label_head)
            cv2.imshow('age_sex_detection', image_head)

            # faces searching
            image_face = cv2.cvtColor(image_head, cv2.COLOR_BGR2GRAY)
            image_face = cv2.cvtColor(image_face, cv2.COLOR_GRAY2RGB)
            faces = face_classifier.detectMultiScale(image_face, minNeighbors=FACE_CLASSIFIER_MIN_NEIGHBORS, minSize=FACE_CLASSIFIER_MIN_SIZE)

            if len(faces) == 0:
                continue

            x, y, w, h = faces[0]

            # face cutting
            image_face = image_face[y:y + h, x:x + w]

            # some image processing and kostyls
            image_face_resized = cv2.resize(image_face, (48, 48), interpolation=cv2.INTER_AREA)
            roi = np.empty((1, 48, 48, 3))
            roi[0] = image_face_resized
            roi = roi / 255

            #prediction making
            prediction = classifier.predict(roi)
            emotion_label = EMOTION_LABELS[np.argmax(prediction)]
            worker[emotion_label] += 1

            # prediction drawing
            label_position = (x, y)
            cv2.putText(image_face, emotion_label, label_position, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
            cv2.imshow('Emotion Detector', image_face)

        if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    worker["age_group"] = int(age_avg)
    worker["sex"] = bool(sex_avg > 0.5)
    service_time = int(time.time() - session_start_time)
    worker["consultation_time"] = service_time
    worker["date"] = int(datetime.now().timestamp())
    mq_send(json.dumps(worker))
    try_detect_frame(worker_id, video_driver_path, cap, client_number if service_time < 10 else client_number + 1)

face_classifier = cv2.CascadeClassifier(paths.FACE_CLASSIFIER_PATH)  # детектор лица OpenCV
classifier = load_model(paths.PREDICTION_MODEL_PATH)  # обученная модель для классификации эмоций

with open(paths.CONFIG_PATH, "r") as stream:
    try:
        config = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)


send_period_s = int(config['send_period_s'])
# for worker in config['workers']:
#     worker_id = int(worker['id'])
#     video_driver_path = worker['video_driver_path']
#     Thread(target=try_detect_frame, kwargs={'worker_id': worker_id, 'video_driver_path': video_driver_path}).run()

worker = config['workers'][0]
worker_id = int(worker['id'])
video_driver_path = worker['video_driver_path']
cap = cv2.VideoCapture(video_driver_path)
try_detect_frame(worker_id, video_driver_path, cap, 1)

print("end")
cv2.destroyAllWindows()
