# Motion Detector → Hikvision NVR

RTSP IP cams → OpenCV motion → Hikvision ISAPI recording.

### Why?
Most cheap Chinese cameras (P05, etc.) only support **their cloud or SD card**. I had a Hikvision NVR—**why not use its HDD?**

**Problem:** NVR "sees" camera but **motion detection fails**:
- Camera "motion" doesn't send proper ONVIF alerts
- NVR ignores → no recording

**Solution:** OpenCV detects motion → **triggers NVR recording** via ISAPI. Profit!

## Quickstart
```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
python3 detector.py

## Features
| Feature          | Description                                        |
| ---------------- | -------------------------------------------------- |
| Multi-Camera     | Unlimited parallel RTSP cams (config.yaml)         |
| Motion Detection | OpenCV frame diff + contours (>threshold px²)      |
| Smart Recording  | NVR manual start → auto-stop after quiet (per-cam) |
| Stable           | TCP reconnect, substream, 1-frame buffer           |
| Hikvision        | /ISAPI/.../tracks/101 → Ch1 HDD clips              |