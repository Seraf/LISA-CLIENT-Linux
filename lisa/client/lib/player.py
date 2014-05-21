# -*- coding: UTF-8 -*-

# Imports
import gst
import os
import time
from time import sleep

# Current path
PWD = os.path.dirname(os.path.abspath(__file__ + '/..'))

# Create a gtreamer playerbin
__PLAYER__ = gst.element_factory_make("playbin", "player")

def play(sound, path=None, ext=None):
    """
    Play a sound. Determine path and extension if not provided.
    """
    global PWD
    global __PLAYER__
    
    # Stop previous play if any
    __PLAYER__.set_state(gst.STATE_NULL)

    # Get path
    if not path:
        path = "%s/sounds" % PWD

    # Search extension
    if ext and os.path.isfile('%s/%s.%s' % (path, sound, ext)):
        filename = '%s/%s.%s' % (path, sound, ext)
    elif os.path.isfile('%s/%s.wav' % (path, sound)):
        filename = '%s/%s.wav' % (path, sound)
    elif os.path.isfile('%s/%s.ogg' % (path, sound)):
        filename = '%s/%s.ogg' % (path, sound)
    else:
        filename = '%s/pi-cancel.wav' % path

    # Play file
    __PLAYER__.set_property('uri', 'file://%s' % filename)
    __PLAYER__.set_state(gst.STATE_PLAYING)

def play_block(sound, path=None, ext=None):
    global __PLAYER__

    play(sound = sound, path = path, ext = ext)
    #TODO This code doesn't block
    #while __PLAYER__.get_state() == gst.STATE_PLAYING:
    #    sleep(.1)
