import os
import argparse
import signal
import sys
import json
import uuid
import player
from connect_ffi import ffi, lib, C
from console_callbacks import audio_arg_parser, audio_player, play_event, pause_event, error_callback, connection_callbacks, debug_callbacks, playback_callbacks
from utils import print_zeroconf_vars

class Connect:
    def __init__(self, error_cb = error_callback):
        pass_required = False
        if __name__ == "__main__":
            #Require username and password when used without a web server
            pass_required = True
        arg_parser = argparse.ArgumentParser(description='Web interface for Spotify Connect', parents=[audio_arg_parser])
        arg_parser.add_argument('--debug', '-d', help='enable libspotify_embedded/flask debug output', action="store_true")
        arg_parser.add_argument('--key', '-k', help='path to spotify_appkey.key', default='spotify_appkey.key', type=file)
        arg_parser.add_argument('--username', '-u', help='your spotify username', required=pass_required)
        arg_parser.add_argument('--password', '-p', help='your spotify password', required=pass_required)
        arg_parser.add_argument('--name', '-n', help='name that shows up in the spotify client', default='TestConnect')
        arg_parser.add_argument('--bitrate', '-b', help='Sets bitrate of audio stream (may not actually work)', choices=[90, 160, 320], type=int, default=160)
        arg_parser.add_argument('--credentials', '-c', help='File to load and save credentials from/to', default='credentials.json')
        self.args = arg_parser.parse_args()

        app_key = ffi.new('uint8_t *')
        self.args.key.readinto(ffi.buffer(app_key))
        app_key_size = len(self.args.key.read()) + 1

        self.credentials = dict({
            'device-id': str(uuid.uuid4()),
            'username': None,
            'blob': None
        })

        try:
            with open(self.args.credentials) as f:
                self.credentials.update(
                        { k: v.encode('utf-8') if isinstance(v, unicode) else v
                            for (k,v)
                            in json.loads(f.read()).iteritems() })
        except IOError:
            pass

        if self.args.username:
            self.credentials['username'] = self.args.username

        userdata = ffi.new_handle(self)

        self.config = {
             'version': 4,
             'buffer': C.malloc(0x100000),
             'buffer_size': 0x100000,
             'app_key': app_key,
             'app_key_size': app_key_size,
             'deviceId': ffi.new('char[]', self.credentials['device-id']),
             'remoteName': ffi.new('char[]', self.args.name),
             'brandName': ffi.new('char[]', 'DummyBrand'),
             'modelName': ffi.new('char[]', 'DummyModel'),
             'deviceType': lib.kSpDeviceTypeAudioDongle,
             'error_callback': error_cb,
             'userdata': userdata,
        }

        init = ffi.new('SpConfig *' , self.config)
        print "SpInit: {}".format(lib.SpInit(init))

        lib.SpRegisterConnectionCallbacks(connection_callbacks, userdata)
        if self.args.debug:
            lib.SpRegisterDebugCallbacks(debug_callbacks, userdata)
        lib.SpRegisterPlaybackCallbacks(playback_callbacks, userdata)
        
        try:
            audio_player.mixer_load()
            mixer_volume = int(audio_player.get_volume() * 655.35)
            lib.SpPlaybackUpdateVolume(mixer_volume)
        except player.MixerError as error:
            print error

        bitrates = {
            90: lib.kSpBitrate90k,
            160: lib.kSpBitrate160k,
            320: lib.kSpBitrate320k
        }

        lib.SpPlaybackSetBitrate(bitrates[self.args.bitrate])

        print_zeroconf_vars()

        if self.credentials['username'] and self.args.password:
            self.login(password=self.args.password)
        elif self.credentials['username'] and self.credentials['blob']:
            self.login(blob=self.credentials['blob'])

    def login(self, username=None, password=None, blob=None, zeroconf=None):
        if username is not None:
            self.credentials['username'] = username
        elif self.credentials['username']:
            username = self.credentials['username']
        else:
            raise ValueError("No username given, and none stored")

        if password is not None:
            lib.SpConnectionLoginPassword(username, password)
        elif blob is not None:
            lib.SpConnectionLoginBlob(username, blob)
        elif zeroconf is not None:
            lib.SpConnectionLoginZeroConf(username, *zeroconf)
        else:
            raise ValueError("Must specify a login method (password, blob or zeroconf)")
        
    def check_events(self):
        if play_event.is_set() and not audio_player.playing():
            if not audio_player.acquired():
                try:
                    audio_player.acquire()
                    print "DeviceAcquired"
                    audio_player.play()
                except player.DeviceError as error:
                    print error
                    lib.SpPlaybackPause()
            else:
                audio_player.play()
        elif pause_event.is_set() and audio_player.playing():
            audio_player.pause()
            audio_player.release()
            print "DeviceReleased"
                
        play_event.clear()
        pause_event.clear()
    
def signal_handler(signal, frame):
        lib.SpConnectionLogout()
        lib.SpFree()
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

#Only run if script is run directly and not by an import
if __name__ == "__main__":
    @ffi.callback('void(SpError err, void *userdata)')
    def console_error_callback(error, userdata):
        if error == lib.kSpErrorLoginBadCredentials:
            print 'Invalid username or password'
            #sys.exit() doesn't work inside of a ffi callback
            C.exit(1)
        else:
            error_callback(msg)
    connect = Connect(console_error_callback)

    while 1:
        lib.SpPumpEvents()
        connect.check_events()
