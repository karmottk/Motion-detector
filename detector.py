#!/usr/bin/env python3
import os
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000|reconnect;1|reconnect_stream;1"
os.environ['OPENCV_LOG_LEVEL'] = 'FATAL'

import cv2
import numpy as np
import requests
import time
import threading
import yaml  # pip install pyyaml
from datetime import datetime
from collections import defaultdict
from pathlib import Path


# Load config
CONFIG_PATH = Path("config.yaml")
if not CONFIG_PATH.exists():
    print(f"❌ Missing {CONFIG_PATH}. Copy config.example.yaml → config.yaml and edit!")
    exit(1)

with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

NVR_IP = config['nvr']['ip']
NVR_USER = config['nvr']['user']
NVR_PASS = config['nvr']['pass']
CAMERAS = config['cameras']
COOLDOWN = config['cooldown']


# Globals
running = True
recording_state = defaultdict(bool)
last_motion_time = defaultdict(float)


def stop_record(track_id, cam_name):
    stop_url = f'http://{NVR_IP}/ISAPI/ContentMgmt/record/control/manual/stop/tracks/{track_id}'
    try:
        resp = requests.put(stop_url, auth=(NVR_USER, NVR_PASS), timeout=5)
        print(f'{cam_name}: Recording STOPPED [{resp.status_code}]')
        recording_state[cam_name] = False
    except Exception as e:
        print(f'{cam_name}: Stop record failed: {e}')


def send_nvr_record(cam):
    cam_name = cam['name']
    now = time.time()
    
    if recording_state[cam_name]:
        return
    
    if now - last_motion_time[cam_name] < COOLDOWN:
        return
    
    track_id = cam['nvr_channel'] * 100 + 1
    start_url = f'http://{NVR_IP}/ISAPI/ContentMgmt/record/control/manual/start/tracks/{track_id}'
    
    try:
        resp_start = requests.put(start_url, auth=(NVR_USER, NVR_PASS), timeout=5)
        print(f'{cam_name}: Recording STARTED Ch{cam["nvr_channel"]} [{resp_start.status_code}]')
        recording_state[cam_name] = True
        last_motion_time[cam_name] = now
    except Exception as e:
        print(f'{cam_name}: Record failed: {e}')
        return
    
    check_thread = threading.Thread(target=monitor_no_motion_stop, args=(cam,), daemon=True)
    check_thread.start()


def monitor_no_motion_stop(cam):
    cam_name = cam['name']
    timeout = cam['no_motion_timeout']
    
    while running and recording_state[cam_name]:
        now = time.time()
        if now - last_motion_time[cam_name] > timeout:
            track_id = cam['nvr_channel'] * 100 + 1
            stop_record(track_id, cam_name)
            break
        time.sleep(1)


class CameraProcessor:
    def __init__(self, cam):
        self.cam = cam
        self.cap = None
        self.ref_frame = None
        self.frame_count = 0
        self.reconnects = 0
        self.cam_name = cam['name']
        
    def init_cap(self):
        self.cap = cv2.VideoCapture(self.cam['rtsp'], cv2.CAP_FFMPEG)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 15)
            return True
        return False
    
    def process(self):
        while running:
            if self.cap is None or not self.cap.isOpened():
                print(f"{self.cam_name}: Reconnecting... (#{self.reconnects})")
                if self.cap:
                    self.cap.release()
                if self.init_cap():
                    self.reconnects += 1
                    print(f"{self.cam_name}: Connected")
                else:
                    time.sleep(2)
                    continue
            
            ret, frame = self.cap.read()
            self.frame_count += 1
            if not ret:
                continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            if self.ref_frame is None:
                self.ref_frame = gray.copy()
                print(f"{self.cam_name}: Reference set")
                continue
            
            delta = cv2.absdiff(self.ref_frame, gray)
            thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            motion_area = sum(cv2.contourArea(c) for c in contours)
            if motion_area > self.cam['threshold']:
                if not recording_state[self.cam_name]:
                    print(f'{self.cam_name}: Motion detected {motion_area:.0f}px [{self.frame_count}] {datetime.now()}')
                threading.Thread(target=send_nvr_record, args=(self.cam,), daemon=True).start()
                last_motion_time[self.cam_name] = time.time()
            
            low_motion = motion_area < (self.cam['threshold'] * 0.1)
            if self.frame_count % 300 == 0 or low_motion:
                self.ref_frame = gray.copy()
                if low_motion and self.frame_count % 30 == 0:
                    print(f"{self.cam_name}: Background updated (quiet)")
            
            time.sleep(0.033)
        
        if self.cap:
            self.cap.release()


if __name__ == '__main__':
    print("Starting motion detectors...")
    processors = {cam['name']: CameraProcessor(cam) for cam in CAMERAS}
    
    threads = []
    for proc in processors.values():
        t = threading.Thread(target=proc.process, daemon=True)
        t.start()
        threads.append(t)
        print(f"{proc.cam_name}: Thread started")
    
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        running = False
        print("Stopped all cams")
