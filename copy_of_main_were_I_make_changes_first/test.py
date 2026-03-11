import random
import cv2
import threading
import multiprocessing
from multiprocessing import Queue
import time
from fastapi.responses import StreamingResponse
from ultralytics import YOLO
import os
from fastapi import FastAPI, HTTPException
from app.database.db import Post, create_db_and_tables, get_async_session, Mission
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from app.utils.imagekitupload import imagekit
import tempfile
import imagehash
from PIL import Image
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware

# ----------------------------
# GLOBAL QUEUES
# ----------------------------

frame_queue = Queue(maxsize=10)
annotation_queue = Queue(maxsize=10)
crop_queue = Queue(maxsize=10)
result_queue = Queue()
final_batch = Queue()

stream_url = "rtsp://172.25.173.19:8080/h264.sdp"

# ----------------------------
# GEOLOCATION MOCK
# ----------------------------

def geolocation():
    return {
        "lat": random.random(),
        "long": random.random()
    }

# ----------------------------
# STREAM CLASS
# ----------------------------

class Stream:

    def __init__(self, source, frame_queue):
        self.source = source
        self.frame_queue = frame_queue
        self.capture = cv2.VideoCapture(self.source)
        self.stopFlag = False
        self.thread = threading.Thread(target=self.update, daemon=True)

    def start(self):
        print("Stream thread started")
        self.thread.start()

    def update(self):

        while not self.stopFlag:

            ret, frame = self.capture.read()

            if not ret:
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # resize for faster inference
            frame = cv2.resize(frame, (640, 640))

            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass

            self.frame_queue.put(frame)

            time.sleep(0.01)

    def stop(self):
        self.stopFlag = True
        self.capture.release()

# ----------------------------
# BATCH PROCESS
# ----------------------------

def batch_storing_process(frame_queue, final_batch):

    batch_frames = []
    last_flush = time.time()

    BATCH_SIZE = 3
    MAX_WAIT = 0.05

    while True:

        frame = frame_queue.get()
        batch_frames.append(frame)

        now = time.time()

        if len(batch_frames) >= BATCH_SIZE or (now - last_flush) > MAX_WAIT:

            final_batch.put(batch_frames)
            batch_frames = []
            last_flush = now

# ----------------------------
# YOLO PROCESS
# ----------------------------

def yolo_process(final_batch, annotation_queue, crop_queue):

    model = YOLO("yolo26n.pt")

    saved_ids = set()
    seen_frames = {}

    STABLE_FRAMES = 10

    while True:

        frames = final_batch.get()

        results = model.track(
            source=frames,
            persist=True,
            classes=[0],
            conf=0.15,
            verbose=False
        )

        for frame, r in zip(frames, results):

            annotated = r.plot()

            if annotation_queue.full():
                try:
                    annotation_queue.get_nowait()
                except:
                    pass

            annotation_queue.put(annotated)

            if r.boxes.id is None:
                continue

            for box in r.boxes:

                track_id = int(box.id[0])

                seen_frames[track_id] = seen_frames.get(track_id, 0) + 1

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                if seen_frames[track_id] >= STABLE_FRAMES and track_id not in saved_ids:

                    saved_ids.add(track_id)

                    crop = frame[y1:y2, x1:x2]

                    if crop.size == 0:
                        continue

                    if crop_queue.full():
                        try:
                            crop_queue.get_nowait()
                        except:
                            pass

                    crop_queue.put((track_id, crop))

# ----------------------------
# STORAGE PROCESS
# ----------------------------

def storage_process(crop_queue, result_queue, shared_state):

    duplicate_phash = set()

    print("Storage process started")

    while True:

        track_id, detect_image = crop_queue.get()

        mission_id = shared_state.get("mission_id")

        if mission_id is None:
            continue

        geo = geolocation()

        latitude = geo["lat"]
        longitude = geo["long"]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:

            temp_name = f.name
            cv2.imwrite(temp_name, detect_image)

        image = Image.open(temp_name)
        phash = imagehash.phash(image)

        if phash in duplicate_phash:

            os.remove(temp_name)
            continue

        duplicate_phash.add(phash)

        with open(temp_name, "rb") as f:

            response = imagekit.files.upload(
                file=f,
                file_name=f"{track_id}.jpg",
                folder=f"/{mission_id}"
            )

        result_queue.put({
            "mission_id": mission_id,
            "url": response.url,
            "file_name": f"{track_id}.jpg",
            "latitude": latitude,
            "longitude": longitude
        })

        os.remove(temp_name)

# ----------------------------
# FASTAPI LIFESPAN
# ----------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Starting system...")

    await create_db_and_tables()

    manager = multiprocessing.Manager()

    app.state.shared_state = manager.dict()
    app.state.shared_state["mission_id"] = None

    app.state.stream = None
    app.state.yolo_proc = None
    app.state.storage_proc = None
    app.state.batch_proc = None

    yield

    if app.state.stream:
        app.state.stream.stop()

    if app.state.yolo_proc:
        app.state.yolo_proc.terminate()

    if app.state.storage_proc:
        app.state.storage_proc.terminate()

    if app.state.batch_proc:
        app.state.batch_proc.terminate()

# ----------------------------
# FASTAPI APP
# ----------------------------

app = FastAPI(lifespan=lifespan)

origins = ["http://127.0.0.1:5500"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# STREAM ENDPOINT
# ----------------------------

@app.get("/stream")
def stream_video():

    def generate():

        while True:

            annotated = annotation_queue.get()

            ret, buffer = cv2.imencode(".jpg", annotated)

            if not ret:
                continue

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                buffer.tobytes() +
                b'\r\n'
            )

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ----------------------------
# START MISSION
# ----------------------------

@app.post("/Mission")
async def start_mission(db: AsyncSession = Depends(get_async_session)):

    new_mission = Mission()
    db.add(new_mission)

    await db.commit()
    await db.refresh(new_mission)

    mission_id = new_mission.id
    app.state.shared_state["mission_id"] = mission_id

    if app.state.stream is None:

        app.state.stream = Stream(stream_url, frame_queue)
        app.state.stream.start()

    if app.state.batch_proc is None:

        app.state.batch_proc = multiprocessing.Process(
            target=batch_storing_process,
            args=(frame_queue, final_batch),
            daemon=True
        )

        app.state.batch_proc.start()

    if app.state.yolo_proc is None:

        app.state.yolo_proc = multiprocessing.Process(
            target=yolo_process,
            args=(final_batch, annotation_queue, crop_queue),
            daemon=True
        )

        app.state.yolo_proc.start()

    if app.state.storage_proc is None:

        app.state.storage_proc = multiprocessing.Process(
            target=storage_process,
            args=(crop_queue, result_queue, app.state.shared_state),
            daemon=True
        )

        app.state.storage_proc.start()

    return {
        "status": "mission started",
        "mission_id": mission_id
    }

# ----------------------------
# STOP MISSION
# ----------------------------

@app.post("/stop_mission")
async def stop_mission(db: AsyncSession = Depends(get_async_session)):

    mission_id = app.state.shared_state.get("mission_id")

    if mission_id is None:
        raise HTTPException(status_code=400, detail="No active mission")

    results = []

    while not result_queue.empty():
        results.append(result_queue.get())

    for r in results:

        post = Post(
            mission_id=mission_id,
            url=r["url"],
            file_type="jpg",
            file_name=r["file_name"],
            latitude=r["latitude"],
            longitude=r["longitude"]
        )

        db.add(post)

    await db.commit()

    if app.state.stream:
        app.state.stream.stop()
        app.state.stream = None

    if app.state.yolo_proc:
        app.state.yolo_proc.terminate()
        app.state.yolo_proc = None

    if app.state.storage_proc:
        app.state.storage_proc.terminate()
        app.state.storage_proc = None

    if app.state.batch_proc:
        app.state.batch_proc.terminate()
        app.state.batch_proc = None

    app.state.shared_state["mission_id"] = None

    return {
        "status": "mission stopped",
        "detections_saved": len(results)
    }