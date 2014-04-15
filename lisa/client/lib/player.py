import gst
import os

PWD = os.path.dirname(os.path.abspath(__file__ + '/..'))
__PLAYER__ = gst.element_factory_make("playbin", "player")

def play(sound, path=None):
    #global PWD
    global __PLAYER__
    __PLAYER__.set_state(gst.STATE_NULL)
    __PLAYER__ = gst.element_factory_make("playbin", "player")

    if path:
        __PLAYER__.set_property('uri', 'file://%s/%s.wav' % (path, sound))

    __PLAYER__.set_property('uri', 'file://%s/sounds/%s.wav' % (PWD, sound))
    __PLAYER__.set_state(gst.STATE_PLAYING)