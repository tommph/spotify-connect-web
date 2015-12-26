import argparse
import json
import player
from threading import Event
from connect_ffi import ffi, lib

RATE = 44100
CHANNELS = 2
PERIODSIZE = 44100 / 40 # 0.025s
SAMPLESIZE = 2 # 16 bit integer
MAXPERIODS = int(0.5 * RATE / PERIODSIZE) # 0.5s Buffer

audio_arg_parser = argparse.ArgumentParser(add_help=False)
audio_arg_parser.add_argument('--device', '-D', help='alsa output device', default='default')
audio_arg_parser.add_argument('--mixer', '-m', help='alsa mixer name for volume control')
args = audio_arg_parser.parse_known_args()[0]

audio_player = player.Player(args.device, RATE, CHANNELS, PERIODSIZE, MAXPERIODS)

play_event = Event()
pause_event = Event()

def userdata_wrapper(f):
    def inner(*args):
        assert len(args) > 0
        self = ffi.from_handle(args[-1])
        return f(self, *args[:-1])
    return inner

#Error callbacks
@ffi.callback('void(SpError error, void *userdata)')
def error_callback(error, userdata):
    print "error_callback: {}".format(error)

#Connection callbacks
@ffi.callback('void(SpConnectionNotify type, void *userdata)')
@userdata_wrapper
def connection_notify(self, type):
    if type == lib.kSpConnectionNotifyLoggedIn:
        print "kSpConnectionNotifyLoggedIn"
    elif type == lib.kSpConnectionNotifyLoggedOut:
        print "kSpConnectionNotifyLoggedOut"
    elif type == lib.kSpConnectionNotifyTemporaryError:
        print "kSpConnectionNotifyTemporaryError"
    else:
        print "UNKNOWN ConnectionNotify {}".format(type)

@ffi.callback('void(const char *blob, void *userdata)')
@userdata_wrapper
def connection_new_credentials(self, blob):
    print ffi.string(blob)
    self.credentials['blob'] = ffi.string(blob)

    with open(self.args.credentials, 'w') as f:
        f.write(json.dumps(self.credentials))

#Debug callbacks
@ffi.callback('void(const char *msg, void *userdata)')
@userdata_wrapper
def debug_message(self, msg):
    print ffi.string(msg)

#Playback callbacks
@ffi.callback('void(SpPlaybackNotify type, void *userdata)')
@userdata_wrapper
def playback_notify(self, type):
    if type == lib.kSpPlaybackNotifyPlay:
        print "kSpPlaybackNotifyPlay"
    elif type == lib.kSpPlaybackNotifyPause:
        print "kSpPlaybackNotifyPause"
        pause_event.set()
    elif type == lib.kSpPlaybackNotifyTrackChanged:
        print "kSpPlaybackNotifyTrackChanged"
    elif type == lib.kSpPlaybackNotifyNext:
        print "kSpPlaybackNotifyNext"
    elif type == lib.kSpPlaybackNotifyPrev:
        print "kSpPlaybackNotifyPrev"
    elif type == lib.kSpPlaybackNotifyShuffleEnabled:
        print "kSpPlaybackNotifyShuffleEnabled"
    elif type == lib.kSpPlaybackNotifyShuffleDisabled:
        print "kSpPlaybackNotifyShuffleDisabled"
    elif type == lib.kSpPlaybackNotifyRepeatEnabled:
        print "kSpPlaybackNotifyRepeatEnabled"
    elif type == lib.kSpPlaybackNotifyRepeatDisabled:
        print "kSpPlaybackNotifyRepeatDisabled"
    elif type == lib.kSpPlaybackNotifyBecameActive:
        print "kSpPlaybackNotifyBecameActive"
    elif type == lib.kSpPlaybackNotifyBecameInactive:
        print "kSpPlaybackNotifyBecameInactive"
        pause_event.set()
    elif type == lib.kSpPlaybackNotifyPlayTokenLost:
        print "kSpPlaybackNotifyPlayTokenLost"
    elif type == lib.kSpPlaybackEventAudioFlush:
        print "kSpPlaybackEventAudioFlush"
        audio_flush()
    else:
        print "UNKNOWN PlaybackNotify {}".format(type)
        
def audio_flush():
    global pending_data
    
    audio_player.buffer_flush()
    pending_data = str()
    
pending_data = str()

@ffi.callback('uint32_t(const void *data, uint32_t num_samples, SpSampleFormat *format, uint32_t *pending, void *userdata)')
@userdata_wrapper
def playback_data(self, data, num_samples, format, pending):
    global pending_data
    
    play_event.set()
    
    # Make sure we don't pass incomplete frames to alsa
    num_samples -= num_samples % CHANNELS

    buf = pending_data + ffi.buffer(data, num_samples * SAMPLESIZE)[:]

    try:
        total = 0
        while len(buf) >= PERIODSIZE * CHANNELS * SAMPLESIZE:
            audio_player.write(buf[:PERIODSIZE * CHANNELS * SAMPLESIZE])
            buf = buf[PERIODSIZE * CHANNELS * SAMPLESIZE:]
            total += PERIODSIZE * CHANNELS

        pending_data = buf
        return num_samples
    except player.BufferFull:
        return total
    finally:
        pending[0] = audio_player.buffer_length() * PERIODSIZE * CHANNELS

@ffi.callback('void(uint32_t millis, void *userdata)')
@userdata_wrapper
def playback_seek(self, millis):
    print "playback_seek: {}".format(millis)

@ffi.callback('void(uint16_t volume, void *userdata)')
@userdata_wrapper
def playback_volume(self, volume):
    print "playback_volume: {}".format(volume)
    if audio_player.mixer_loaded():
        audio_player.set_volume(int(volume / 655.35))

connection_callbacks = ffi.new('SpConnectionCallbacks *', [
    connection_notify,
    connection_new_credentials
])

debug_callbacks = ffi.new('SpDebugCallbacks *', [
    debug_message
])

playback_callbacks = ffi.new('SpPlaybackCallbacks *', [
    playback_notify,
    playback_data,
    playback_seek,
    playback_volume
])
