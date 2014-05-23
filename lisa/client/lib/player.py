# -*- coding: UTF-8 -*-

# Imports
import gst
import os
import time
from time import sleep
import gobject
gobject.threads_init()


# Current path
PWD = os.path.dirname(os.path.abspath(__file__ + '/..'))

# Create a gtreamer playerbin
__PLAYER__ = None

# Connect End Of Stream handler on bus
main_loop = gobject.MainLoop()
def eos_handler(bus, message):
    __PLAYER__.set_state(gst.STATE_READY)
    main_loop.quit()


def play(sound, path=None, ext=None):
    """
    Play a sound. Determine path and extension if not provided.
    """
    global PWD
    global __PLAYER__

    # Create player once
    if __PLAYER__ is None:
        __PLAYER__ = gst.element_factory_make("playbin2", "player")
        
        # Connect End Of Stream handler on bus
        bus = __PLAYER__.get_bus()
        bus.add_signal_watch()
        bus.connect('message::eos', eos_handler)

    # Stop previous play if any
    else:
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


def play_block(sound, path=None, ext=None):
    """
    Play sound but block until end
    """
    global main_loop

    # Play sound
    play(sound = sound, path = path, ext = ext)

    # Wait for EOS signal in mail loop
    main_loop.run()


def play_free():
    """
    Free player
    """
    global __PLAYER__
    
    # Delete player
    if __PLAYER__ is not None:
        __PLAYER__.set_state(gst.STATE_NULL)
        __PLAYER__ = None
