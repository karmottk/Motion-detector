### Motion Detector
Motion detector for Digicam P05 cameras and Hikvision DS-7600 NVR.
Detect motion -> Send manual record to NVR -> motion not detected for 10 seconds -> stop recording -> profit.

### USAGE 
```
pip install -r requirements.txt
cp config.example.yaml config.yaml  # Edit RTSP/creds!
python3 detector.py
```
