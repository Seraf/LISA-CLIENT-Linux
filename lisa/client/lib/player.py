# -*- coding: UTF-8 -*-

# Imports
import gst
import os
import time
from time import sleep
from threading import Lock

mutex = Lock()
# Current path
PWD = os.path.dirname(os.path.abspath(__file__ + '/..'))

# Playback mutex : locked during play
_mutex = Lock()
def _on_about_to_finish(user):
    _mutex.release()
    
# Create a gtreamer playerbin
__PLAYER__ = gst.element_factory_make("playbin2", "player")
__PLAYER__.connect('about-to-finish', _on_about_to_finish)

def play(sound, path=None, ext=None):
    """
    Play a sound. Determine path and extension if not provided.
    """
    global PWD
    global __PLAYER__
    
    # Stop previous play if any
    __PLAYER__.set_state(gst.STATE_READY)

    # Get path
    if not path:
        path = "%s/sounds" % PWD

    # Search extension
    if os.path.isfile(sound):
        filename = sound
    elif ext is not None and os.path.isfile('%s/%s.%s' % (path, sound, ext)):
        filename = '%s/%s.%s' % (path, sound, ext)
    elif os.path.isfile('%s/%s.wav' % (path, sound)):
        filename = '%s/%s.wav' % (path, sound)
    elif os.path.isfile('%s/%s.ogg' % (path, sound)):
        filename = '%s/%s.ogg' % (path, sound)
    elif os.path.isfile('/tmp/%s.wav' % sound):
        filename = '/tmp/%s.wav' % sound
    elif os.path.isfile('/tmp/%s.ogg' % sound):
        filename = '/tmp/%s.ogg' % sound
    else:
        filename = '%s/sounds/pi-cancel.wav' % PWD

    # Play file
    __PLAYER__.set_property('uri', 'file://%s' % filename)
    __PLAYER__.set_state(gst.STATE_PLAYING)
    
    # Locked mutex if not already done
    _mutex.acquire(0)


def play_block(sound, path=None, ext=None):
    """
    Play sound but block until end
    """
    # Play sound
    play(sound = sound, path = path, ext = ext)

    # Waits end of playback
    _mutex.acquire()
    _mutex.release()

    # Gstreamer about-to-finish message is occuring before real end, so wait a little more
    sleep(.5)
