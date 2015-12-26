import alsaaudio as alsa
import Queue
from threading import Thread, Event

class Player:
    def __init__(self, device, rate, channels, periodsize, buffer_length):    
        self.device = None
        self.device_name = device
        self.rate = rate
        self.channels = channels
        self.periodsize = periodsize
        
        self.mixer = None
    
        self.queue = Queue.Queue(maxsize=buffer_length)
        self.t = Thread()
        
    def mixer_load(self, mixer = ""):
        if not mixer:
            try:
                device_mixers = alsa.mixers(device = self.device_name)
            except alsa.ALSAAudioError as error:
                raise "PlayerError: {}".format(error)
                
            if len(device_mixers) > 0:
                mixer = device_mixers[0]
            else:
                raise PlayerError("PlayerError: Device has no mixers")
        
        try:
            self.mixer = alsa.Mixer(mixer, device = self.device_name)
        except alsa.ALSAAudioError as error:
            raise PlayerError("PlayerError: {}".format(error))
            
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
            raise PlayerError("PlayerError: {}".format(error))
            
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
        
class PlayerError(Exception):
    pass

class BufferFull(Exception):
    pass