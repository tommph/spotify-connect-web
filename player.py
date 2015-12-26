import alsaaudio as alsa
import Queue
from threading import Thread, Event

class Player:
    def __init__(self, buffer_length, device, rate, channels, periodsize, mixer):    
        self.device = None
        self.device_name = device
        self.rate = rate
        self.channels = channels
        self.periodsize = periodsize
        
        self.mixer = None  
        self.mixer_name = mixer
    
        self.queue = Queue.Queue(maxsize=buffer_length)
        self.t = Thread()
        
    def mixer_load(self):
        try:
            self.mixer = alsa.Mixer(self.mixer_name)
        except alsa.ALSAAudioError as error:
            raise MixerError("MixerError: {}".format(error))
            
    def mixer_unload(self):
        self.mixer.close()
        self.mixer = None
                
    def mixer_loaded(self):
        if self.mixer is not None:
            return True
        else:
            return False
            
    def acquire(self):
        try:
            self.device = alsa.PCM(alsa.PCM_PLAYBACK, device = self.device_name)
            self.device.setchannels(self.channels)
            self.device.setrate(self.rate)
            self.device.setperiodsize(self.periodsize)
            self.device.setformat(alsa.PCM_FORMAT_S16_LE)
        except alsa.ALSAAudioError as error:
            raise DeviceError("DeviceError: {}".format(error))
            
    def release(self):
        self.device.close()
        self.device = None
            
    def acquired(self):
        if self.device is not None:
            return True
        else:
            return False

    def playback_thread(self, q, e):
        while not e.is_set():
            data = q.get()
            if data:
                self.device.write(data)
            q.task_done()

    def play(self):
        self.t_stop = Event()
        self.t = Thread(args=(self.queue, self.t_stop), target=self.playback_thread)
        self.t.daemon = True
        self.t.start()
    
    def pause(self):
        self.t_stop.set()
        
        if self.queue.empty():
            self.queue.put(str())
            
        self.t.join()
        
    def playing(self):
        if self.t.isAlive():
            return True
        else:
            return False
            
    def write(self, data):            
        try:
            self.queue.put(data, block=False)
        except Queue.Full:
            raise BufferFull()
            
    def queue_clear(self):
        while not self.queue.empty():
            self.queue.get()
            self.queue.task_done()
            
    def buffer_flush(self):
        if self.playing():
            self.pause()
    
        while not self.queue.empty():
            self.queue.get()
            self.queue.task_done()
                
    def buffer_length(self):
        return self.queue.qsize()
            
    def get_volume(self):
        return self.mixer.getvolume()[0]
        
    def set_volume(self, volume):
        self.mixer.setvolume(volume)
        
class DeviceError(Exception):
    pass

class MixerError(Exception):
    pass

class BufferFull(Exception):
    pass