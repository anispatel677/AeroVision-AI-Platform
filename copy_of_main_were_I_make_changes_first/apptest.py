import random
import cv2
import numpy as np
import threading
import multiprocessing
from multiprocessing import Queue
import time
from fastapi.responses import StreamingResponse
from ultralytics import YOLO
import os
from fastapi import FastAPI, HTTPException
from app.database.db import Post, create_db_and_tables, get_async_session , Mission
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from app.utils.imagekitupload import imagekit
import tempfile
import imagehash 
from PIL import Image
from fastapi import Depends
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.database.db import engine
origins = [
    "http://127.0.0.1:5500",
]


@asynccontextmanager
async def lifespan(app:FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app = FastAPI()


def geolocation():
    return {
        "lat": random.random(),
        "long": random.random()
    }
# def get_yt_stream_url(youtube_url):
#     ydl_opts = {'format': 'best[ext=mp4]', 'quiet': True}
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         info = ydl.extract_info(youtube_url, download=False)
#         return info['url']

# stream_url = get_yt_stream_url("https://www.youtube.com/watch?v=IlnLbDi52zo")

# ----------------------------
# GLOBAL QUEUES (SAFE)
# ----------------------------
frame_queue = Queue(maxsize=10)
annotation_queue = Queue(maxsize=10)
crop_queue = Queue(maxsize=10)
track_queue = Queue(maxsize = 10)
stream_url = "rtsp://172.25.173.19:8080/h264.sdp"



# ----------------------------
# STREAM (FRAME PRODUCER)
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

            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass

            self.frame_queue.put(frame)
            # time.sleep(0.01)

    def stop(self):
        self.stopFlag = True
        self.capture.release()


# ----------------------------
# YOLO PROCESS (FRAME CONSUMER)
# ----------------------------
def yolo_process(frame_queue, annotation_queue, crop_queue):

    print("YOLO process started")

    model = YOLO("yolov8n.pt")
    saved_ids = set()
    seen_frames = {}
    STABLE_FRAMES = 10

    while True:
        frame = frame_queue.get()

        results = model.track(
            source=frame,
            persist=True,
            classes=[0],
            conf=0.15,
            verbose=False
        )

        r = results[0]
        annotated = r.plot()

        # Keep latest annotated frame
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

            if (
                seen_frames[track_id] == STABLE_FRAMES
                and track_id not in saved_ids
            ):
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

                



from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):

    # ----------------------------
    # STARTUP SECTION
    # ----------------------------
    print("Starting system...")

    # Start Stream
    app.state.stream = Stream(stream_url, frame_queue)
    app.state.stream.start()

    # Start YOLO subprocess
    app.state.yolo_proc = multiprocessing.Process(
        target=yolo_process,
        args=(frame_queue, annotation_queue, crop_queue),
        daemon=True
    )
    app.state.yolo_proc.start()

    print("System started successfully")

    yield  # App runs here

    # ----------------------------
    # SHUTDOWN SECTION
    # ----------------------------
    print("Shutting down system...")

    if hasattr(app.state, "stream"):
        app.state.stream.stop()

    if hasattr(app.state, "yolo_proc"):
        app.state.yolo_proc.terminate()
        app.state.yolo_proc.join()

    print("System stopped safely")


# Create app with lifespan
app = FastAPI(lifespan=lifespan)
# ----------------------------
# STREAM ENDPOINT
# ----------------------------
@app.get("/stream")
def stream_video():

    def generate():
        while True:

            annotated = None

            # Always get latest frame
            while not annotation_queue.empty():
                annotated = annotation_queue.get()

            if annotated is None:
                time.sleep(0.01)
                continue

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


# # ----------------------------
# # CLEAN SHUTDOWN
# # ----------------------------
# @app.on_event("shutdown")
# def shutdown_event():

#     if hasattr(app.state, "stream"):
#         app.state.stream.stop()

#     if hasattr(app.state, "yolo_proc"):
#         app.state.yolo_proc.terminate()
#         # app.state.yolo_proc.join()

#     print("System stopped safely")

# duplicate_phash = set()
# @app.post("/Mission")
# async def EACH_DETECTION(db: AsyncSession = Depends(get_async_session)):
#     new_mission = Mission()
#     db.add(new_mission)
#     await db.commit()
#     await db.refresh(new_mission)
#     mission_id = new_mission.id
#     while not Stream.stopFlag:
#         while not crop_queue.empty and track_queue.empty:
#             detect_image = crop_queue.get()
#             track_id = track_queue.get()
#             geo_loc = geo_location()
#             latitude = geo_loc["latitude"]
#             longitude = geo_loc["longitude"]
#             duplicate_flag = False

#             with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
#                 temp_name = f.name
#                 cv2.imwrite(temp_name, detect_image)
#                 image = Image.open(temp_name)
#                 phash = imagehash.phash(image)

#             for dup in duplicate_phash:
#                 if phash == dup:
#                     duplicate_flag = True
#                     break

#             if not duplicate_flag:
#                 duplicate_phash.add(phash)
#                 with open(temp_name, "rb") as f:
#                     response = imagekit.files.upload(
#                         file=f,
#                         file_name=f"{track_id}.jpg",
#                         folder=f"/{mission_id}",
#                         tags=[str(latitude), str(longitude)]
#                     )
#                 new_post = Post(
#                     mission_id=mission_id,
#                     url=response.url,
#                     file_type="jpg",
#                     file_name=f"{track_id}.jpg",
#                     latitude=latitude,
#                     longitude=longitude
#                 )
#                 db.add(new_post)
#                 await db.commit()

#             os.remove(temp_name)
      
#     return {"status": "started", "mission_id": mission_id}
def mission_worker(mission_id):

    duplicate_phash = set()

    while True:
        track_id, detect_image = crop_queue.get()

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

        async def save():
            async with async_sessionmaker(engine)() as db:
                post = Post(
                    mission_id=mission_id,
                    url=response.url,
                    file_type="jpg",
                    file_name=f"{track_id}.jpg",
                    latitude=latitude,
                    longitude=longitude
                )
                db.add(post)
                await db.commit()

        asyncio.run(save())

        os.remove(temp_name)

@app.post("/Mission")
async def start_mission(db: AsyncSession = Depends(get_async_session)):

    new_mission = Mission()
    db.add(new_mission)
    await db.commit()
    await db.refresh(new_mission)

    mission_id = new_mission.id

    thread = threading.Thread(
        target=mission_worker,
        args=(mission_id,),
        daemon=True
    )
    thread.start()

    return {"status": "started", "mission_id": mission_id}

# # @app.post("/Mission")
# # async def EACH_DETECTION(db: AsyncSession = Depends(get_async_session)):
# #     new_mission = Mission()
# #     db.add(new_mission)
# #     await db.commit()
# #     await db.refresh(new_mission)
# #     mission_id = new_mission.id

# #     thread = threading.Thread(target=mission_loop, args=(mission_id,), daemon=True)
# #     thread.start()

# #     return {"status": "started", "mission_id": mission_id}

# # from sqlalchemy import select

# # @app.get("/Mission/{mission_id}")
# # async def get_mission_posts(
# #     mission_id: str,
# #     db: AsyncSession = Depends(get_async_session)
# # ):
# #     result = await db.execute(
# #         select(Post).where(Post.mission_id == mission_id)
# #     )

# #     posts = result.scalars().all()

# #     return [
# #         {
# #             "url": p.url,
# #             "latitude": p.latitude,
# #             "longitude": p.longitude
# #         }
# #         for p in posts
# #     ]
# # @app.get("/debug")
# # async def debug(db: AsyncSession = Depends(get_async_session)):
# #     result = await db.execute(select(Post))
# #     posts = result.scalars().all()
# #     return [
# #         {
# #             "mission_id": p.mission_id,
# #             "url": p.url
# #         }
# #         for p in posts
# #     ]
@app.post("/stop")
def stop_stream():
    Stream.stop()
    return {"status": "stream stopped"}
def mission_loop(mission_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

#     async def run():
#         AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
#         duplicate_phash = set()
#         print("mission loop started")  # 1

#         while not stream.stopFlag:
#             if stream.frame is None:
#                 print("frame is None")  # 2
#                 continue

#             frame = stream.frame.copy()
#             print("got frame, running YOLO")  # 3

#             for detection in YOLO_DETECT(frame):
#                 print(f"detection found: {detection['track_id']}")  # 4
#                 # ... rest of code
        
#         print("mission loop ended, stopFlag:", stream.stopFlag)  # 5

#     loop.run_until_complete(run())
#     loop.close()