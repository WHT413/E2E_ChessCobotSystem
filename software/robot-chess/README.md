# Fairino5 Robot Arm Control with Stockfish AI

## 1. Project Overview
This project implements a **robot arm control system** using the **Fairino5 SDK**, integrated with **Stockfish AI** for chess analysis. The system allows:

- Real-time control of the robot arm using TCP/IP and WebSocket.
- Interaction between a **frontend (Vue.js)**, **backend (Python & Node.js)**, and the robot SDK.
- Automated chess move execution where the robot arm physically moves pieces based on Stockfish AI decisions.
- Real-time monitoring and command visualization through a web interface.

---

## 2. Technologies Used
- **Frontend:** Vue.js (Web UI for monitoring and control)
- **Backend:**
  - Python (robot SDK integration & AI logic)
  - Node.js (WebSocket server & API gateway)
- **Communication:** TCP/IP for direct robot control, WebSocket for real-time frontend updates
- **Robot SDK:** Fairino5 SDK for robotic arm control
- **AI Engine:** Stockfish (for chess move calculation)
- **Database (Optional):** MySQL / SQLite for logging moves and robot state
