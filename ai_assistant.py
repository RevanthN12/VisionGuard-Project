"""
chatbot.py — Vision Guard AI Assistant
A context-aware chatbot for crowd safety Q&A and live system analysis.
"""

import re
import time


CROWD_SAFETY_KB = {
    "stampede": [
        "A stampede occurs when a crowd becomes so dense and panicked that individuals lose control, "
        "leading to fatal crushes. Key warning signs include: panic movement, crowd density > 70%, "
        "sudden directional changes, and screaming/shouting.",
        "To prevent stampedes: maintain crowd density below 4 persons/m², establish clear exit routes, "
        "deploy crowd monitors, use barriers to control flow, and have emergency response teams ready."
    ],
    "crowd density": [
        "Crowd density is measured in persons per square metre (p/m²). "
        "Safe limit is 1–2 p/m². At 4 p/m², movement becomes uncomfortable. "
        "At 6+ p/m², crowd pressure can become dangerous and stampedes can occur.",
        "Vision Guard classifies density into: LOW (<20%), MEDIUM (20–45%), HIGH (45–70%), CRITICAL (>70%). "
        "Immediate intervention is recommended at CRITICAL level."
    ],
    "yolo": [
        "YOLOv8 (You Only Look Once v8) is a state-of-the-art real-time object detection model. "
        "Vision Guard uses YOLOv8n (nano) for fast CPU inference. It detects persons in each frame "
        "with bounding boxes and confidence scores above the threshold.",
        "YOLOv8n can process up to 30 FPS on a modern CPU, making it ideal for real-time surveillance."
    ],
    "optical flow": [
        "Optical Flow (Farneback algorithm) tracks pixel movement between consecutive video frames. "
        "Vision Guard uses it to measure crowd movement speed (pixels/frame) and direction. "
        "High turbulence and fast movement speed are key indicators of panic behaviour.",
        "When movement speed exceeds 14.0 px/frame, the system flags a 'PANIC' level movement event."
    ],
    "risk score": [
        "The Vision Guard Risk Score (0–100%) is computed using a weighted formula: "
        "Density (35%) + Movement (25%) + Behaviour (20%) + Congestion (10%) + Threat (10%). "
        "Scores above 85% trigger a CRITICAL alert.",
        "Risk levels: SAFE (<30%), CAUTION (30–50%), WARNING (50–70%), HIGH RISK (70–85%), CRITICAL (>85%)."
    ],
    "opencv": [
        "OpenCV (Open Source Computer Vision Library) is used in Vision Guard for: "
        "video frame reading, image preprocessing, Farneback optical flow computation, "
        "drawing bounding boxes, and saving evidence snapshots.",
    ],
    "alert": [
        "Vision Guard generates automated alerts when risk thresholds are crossed. "
        "Alerts include: an on-screen banner, an audible alarm sound, a WhatsApp message, "
        "and evidence frame snapshots saved to the outputs folder.",
        "Alerts are logged in the SQLite database with timestamp, risk level, and recommended action."
    ],
    "what to do": [
        "When a HIGH RISK alert occurs: 1) Immediately notify security personnel, "
        "2) Begin controlled evacuation of the zone, 3) Close entry points to stop more people entering, "
        "4) Deploy crowd management barriers, 5) Call emergency services if needed.",
        "Do NOT create panic by making sudden announcements. Use calm, clear instructions "
        "over PA systems to guide people to exit routes."
    ]
}


def _get_context_summary(session_state: dict) -> dict:
    """Extract latest metrics from Streamlit session state."""
    ctx = {
        "people": 0,
        "risk_score": 0,
        "risk_level": "UNKNOWN",
        "density": 0,
        "density_level": "UNKNOWN",
        "movement": 0,
        "movement_level": "UNKNOWN",
        "running": False
    }
    try:
        ctx["running"] = session_state.get("running", False)
        if session_state.get("count_hist"):
            ctx["people"] = list(session_state["count_hist"])[-1]
        if session_state.get("risk_hist"):
            ctx["risk_score"] = list(session_state["risk_hist"])[-1]
        if session_state.get("density_hist"):
            ctx["density"] = list(session_state["density_hist"])[-1]
        # Try to get labels from analyzers
        pred = session_state.get("risk_pred")
        if pred and hasattr(pred, '_last_result') and pred._last_result:
            ctx["risk_level"] = pred._last_result.get("level", "UNKNOWN")
        dens_an = session_state.get("density_an")
        if dens_an:
            ctx["density_level"] = "HIGH" if ctx["density"] > 45 else ("MEDIUM" if ctx["density"] > 20 else "LOW")
        ctx["movement_level"] = "HIGH" if ctx["movement"] > 8 else ("MEDIUM" if ctx["movement"] > 4 else "LOW")
    except Exception:
        pass
    return ctx


def _search_kb(query: str) -> str | None:
    """Search the knowledge base for a relevant answer."""
    q = query.lower()
    best_key = None
    best_score = 0
    for key in CROWD_SAFETY_KB:
        words = key.split()
        score = sum(1 for w in words if w in q)
        if score > best_score:
            best_score = score
            best_key = key
    if best_score > 0:
        answers = CROWD_SAFETY_KB[best_key]
        return answers[0] if len(answers) == 1 else " ".join(answers[:2])
    return None


import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

def _generate_fallback_response(query: str, ctx: dict) -> str:
    q = query.lower().strip()
    
    if any(w in q for w in ["how many people", "person count", "crowd count", "people count", "how many person"]):
        if ctx["running"]:
            return (f"The live monitor is currently detecting **{ctx['people']} people** in the frame. "
                    f"Crowd density is at **{ctx['density']:.0f}%** ({ctx['density_level']} level).")
        return "The monitor is not running. Please press ▶ Start in the sidebar to begin monitoring."

    if any(w in q for w in ["risk", "danger", "safe", "status", "level"]):
        if ctx["running"]:
            lvl = ctx["risk_level"] if ctx["risk_level"] != "UNKNOWN" else ("HIGH RISK" if ctx["risk_score"] > 70 else "SAFE")
            emoji = "🔴" if ctx["risk_score"] > 70 else ("🟡" if ctx["risk_score"] > 30 else "🟢")
            return (f"{emoji} Current Risk Score: **{ctx['risk_score']:.0f}%** — Status: **{lvl}**. "
                    f"People detected: {ctx['people']}, Density: {ctx['density']:.0f}%.")
        return "The monitor is currently stopped. Start monitoring to see live risk scores."

    if any(w in q for w in ["density", "crowded", "packed"]):
        if ctx["running"]:
            return (f"Current crowd density is **{ctx['density']:.0f}%** — classified as **{ctx['density_level']}**. "
                    f"This is based on {ctx['people']} detected persons in the frame area.")
        return "Start the live monitor to see real-time crowd density analysis."

    if any(w in q for w in ["movement", "speed", "motion", "moving"]):
        if ctx["running"]:
            return (f"Current crowd movement speed is measured using Farneback Optical Flow. "
                    f"Movement level: **{ctx['movement_level']}**. "
                    f"High-speed panic movement (>14 px/frame) will trigger a stampede warning.")
        return "Start the live monitor to see movement analysis data."

    if any(w in q for w in ["running", "active", "monitoring", "started"]):
        if ctx["running"]:
            return "✅ Yes, Vision Guard is actively monitoring. Live video analysis is running."
        return "⏹ The system is currently stopped. Click ▶ Start in the sidebar to activate monitoring."

    if any(w in q for w in ["what is vision guard", "about this", "project", "system"]):
        return ("**Vision Guard** is an AI-Driven Stampede Prediction system developed as a Final Year B.E. CSE Project. "
                "It uses YOLOv8 for person detection, Farneback Optical Flow for movement analysis, "
                "a weighted risk engine for stampede prediction, and automated alerts (sound + WhatsApp). "
                "The goal is to improve public safety at crowded venues like events, temples, and stadiums.")

    if any(w in q for w in ["how to start", "how do i start", "how to use", "how to run"]):
        return ("To start monitoring:\n"
                "1. Select a **Video Source** in the left sidebar (Webcam, Upload Video, or Sample).\n"
                "2. Click the **▶ Start** button.\n"
                "3. The AI will begin detecting people, analysing movement, and predicting risk in real time.\n"
                "4. Use the **Simulation toggles** (Panic, Violence, Weapon) to test the alert system.")

    if any(w in q for w in ["whatsapp", "alert", "notification", "message"]):
        return ("Vision Guard sends automatic WhatsApp alerts when the risk reaches HIGH RISK or CRITICAL level. "
                "The message includes the risk score, people count, and evidence image path. "
                "A loud alarm sound also plays from your computer speakers to notify operators immediately.")

    kb_answer = _search_kb(q)
    if kb_answer:
        return kb_answer

    if any(w in q for w in ["hello", "hi", "hey"]):
        status = "actively monitoring the crowd 🟢" if ctx["running"] else "ready to start ⏸"
        return (f"Hello! 👋 I'm the **Vision Guard AI Assistant**. The system is currently **{status}**.\n\n"
                "I can help you with:\n"
                "• **Live data** — current people count, risk level, density\n"
                "• **Crowd safety** — stampede prevention tips\n"
                "• **System info** — how Vision Guard works\n\n"
                "What would you like to know?")

    return ("I'm not sure about that specific question. I can help you with:\n"
            "- **Live system data** (risk level, people count, density)\n"
            "- **Crowd safety** (stampede prevention, evacuation)\n"
            "- **How Vision Guard works** (YOLOv8, optical flow, alerts)\n"
            "Try asking: *'What is the current risk level?'* or *'How does YOLOv8 work?'*")


def generate_response(query: str, session_state: dict) -> str:
    """Generate a context-aware response to the user's query using OpenAI."""
    ctx = _get_context_summary(session_state)
    
    if not OPENAI_API_KEY:
        return _generate_fallback_response(query, ctx)
        
    try:
        system_prompt = (
            "You are the Vision Guard AI Assistant, a smart agent built into an AI-driven crowd safety monitoring system. "
            "You help operators understand the current live crowd status, answer questions about stampede prevention, "
            "and explain how the system works (YOLOv8, Optical Flow). "
            f"Here is the LIVE context right now from the camera:\n"
            f"- System Running: {ctx['running']}\n"
            f"- People Detected: {ctx['people']}\n"
            f"- Risk Score: {ctx['risk_score']}% ({ctx['risk_level']})\n"
            f"- Crowd Density: {ctx['density']}% ({ctx['density_level']})\n"
            f"- Movement Speed: {ctx['movement_level']}\n\n"
            "Be concise, professional, and use markdown. Include emojis where helpful."
        )
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "max_tokens": 300,
            "temperature": 0.5
        }
        
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=8)
        
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            print("[AI Assistant] OpenAI API Error:", resp.text)
            return _generate_fallback_response(query, ctx)
            
    except Exception as e:
        print("[AI Assistant] Request failed:", e)
        return _generate_fallback_response(query, ctx)
