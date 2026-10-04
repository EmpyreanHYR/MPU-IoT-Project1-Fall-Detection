"""Local FFmpeg decoding, including AV1, with original presentation timestamps."""
import json
import subprocess
import threading
import time
import cv2
import numpy as np


class CameraInput:
    """Consume camera frames continuously so inference always uses a fresh image."""
    def __init__(self,index):
        self.camera=cv2.VideoCapture(index)
        if not self.camera.isOpened():raise RuntimeError('Cannot open camera')
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE,1)
        self.condition=threading.Condition();self.frame=None;self.sequence=0;self.consumed=0
        self.closed=False;self.failed=False
        self.thread=threading.Thread(target=self.capture,daemon=True);self.thread.start()
    def capture(self):
        while not self.closed:
            ok,frame=self.camera.read();stamp=time.perf_counter();epoch=time.time()
            with self.condition:
                if not ok:self.failed=True;self.condition.notify_all();break
                self.frame=frame;self.latest_stamp=stamp;self.latest_epoch=epoch;self.sequence+=1
                self.condition.notify_all()
    def read(self):
        with self.condition:
            self.condition.wait_for(lambda:self.sequence>self.consumed or self.failed,timeout=5)
            if self.sequence==self.consumed:return False,None
            self.consumed=self.sequence;self.stamp=self.latest_stamp;self.epoch=self.latest_epoch
            return True,self.frame
    def release(self):
        self.closed=True;self.thread.join(timeout=2);self.camera.release()


class VideoInput:
    def __init__(self,path):
        meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','stream=width,height,codec_name:frame=best_effort_timestamp_time',
            '-of','json',str(path)]))
        stream=meta['streams'][0];self.width=stream['width'];self.height=stream['height']
        self.timestamps=[float(f['best_effort_timestamp_time']) for f in meta['frames']]
        self.index=0;self.stamp=0.
        command=['ffmpeg','-nostdin','-v','error','-threads','2']
        if stream['codec_name']=='av1':command+=['-c:v','libdav1d']
        command+=['-i',str(path),'-map','0:v:0','-an','-vsync','0','-threads','2',
                  '-f','rawvideo','-pix_fmt','bgr24','pipe:1']
        self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    def read(self):
        size=self.width*self.height*3
        raw=self.process.stdout.read(size)
        if len(raw)!=size:
            code=self.process.wait()
            if code:raise RuntimeError('FFmpeg decoding failed')
            return False,None
        self.stamp=self.timestamps[self.index]-self.timestamps[0];self.index+=1
        return True,np.frombuffer(raw,np.uint8).reshape(self.height,self.width,3)
    def release(self):
        self.process.stdout.close()
        if self.process.poll() is None:self.process.terminate()
        self.process.wait()
