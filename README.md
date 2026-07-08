# 🚁 UAV Based Disaster Response System

The **AeroVision AI Platform** is a web-based monitoring and rescue support system designed for the **UAV Based Disaster Response System**. It enables rescue teams to connect their UAVs and monitor live missions through a centralized dashboard.

The platform provides real-time video streaming, live GPS tracking, sensor monitoring, AI-powered survivor detection, and mission visualization to support efficient disaster response operations.

---

## ⚙️ Features

- 📡 Live processed UAV video streaming (RTSP)
- 📍 Real-time UAV GPS tracking (MQTT)
- 🌡️ Live sensor monitoring (temperature)
- 🧠 AI-powered survivor detection using YOLO
- 📸 Automatic capture of detection snapshots with GPS coordinates
- 🗺️ Interactive live mission map
- 📌 Survivor detection markers displayed on the map
- 📦 Cloud storage of detection images using ImageKit.io

---

## 🧩 Tech Stack

- **Frontend:** React
- **Backend:** FastAPI, SQLAlchemy
- **Database:** SQLite
- **AI & Computer Vision:** YOLO (Ultralytics), OpenCV
- **Communication:** MQTT (Mosquitto), PubNub, RTSP
- **Media Storage:** ImageKit.io

---

## 🖼️ Screenshots

![Start Mission](./images/1_start-mission.png)

![Mission Live](./images/2_mission-live.png)

![Detections](./images/3_detections.png)

![Pinpoint Location](./images/4_pin-point%20location.png)

## Picture of Hardware
![Start Mission](./images/UAV-Based-Disaster-Response_System.jpeg)
