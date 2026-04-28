# 🚁 AeroVision-AI-Platform

**AeroVision** is a real-time UAV monitoring and rescue-support platform that enables rescuer to connect their drone and monitor live operations through an centralized dashboard.

It allows rescuers to stream live video from the UAV, view real-time sensor data, detect survivors using AI, and track everything on a live map — all in one unified system.

---

## ⚙️ What It Does

- 📡 Streams **live processed video feed (RTSP)** from the UAV directly to the dashboard  
- 📍 Displays **real-time GPS location (MQTT)** of the drone  
- 🌡️ Shows **live sensor data (MQTT)** such as temperature  
- 🧠 Performs **AI-based object detection (YOLO26)** to identify targets (e.g., survivors)  
- 📸 Captures and displays **detection snapshots with geolocation**  
- 🗺️ Provides a **live tracking map of the UAV**  
- 📌 Marks **detection locations (e.g., survivor positions)** on the map  
- 📦 Stores detection images using **ImageKit.io** for later analysis  

---

## 🧩 Tech Stack

- **Frontend:** React  
- **Backend:** FastAPI, SQLAlchemy  
- **Database:** SQLite
- **AI & Vision:** YOLO (Ultralytics), OpenCV  
- **Communication:** MQTT (Mosquitto), PubNub, RTSP  
- **Media Storage:** ImageKit.io  

---
---

## 🖼️ Screenshots

_Add your project images here_

```md
![Dashboard](./images/dashboard.png)
![Map View](./images/map.png)
![Detections](./images/detections.png)
