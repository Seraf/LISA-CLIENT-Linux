from wit import Wit
import player
from recorder import Recorder

import gobject
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
from twisted.python import log
import json, os

import tempfile
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst

class Listener:
    def __init__(self, lisaclient, botname):
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        configuration = json.load(open(os.path.normpath(dir_path + '/../' + 'configuration/lisa.json')))

        #self.wit = Wit(configuration['wit_token'])
        self.recording_state = False
        self.botname = botname
        self.lisaclient = lisaclient
        self.failed = 0
        self.keyword_identified = 0
        self.recording = '%s/../tmp/google.wav' % dir_path
        self.recorder = None

        # The goal is to listen for a keyword. When I have this keyword, I open the valve and the voice is recorded
        # to the file. Then I submit this file to google/wit, and drop again the flow to not write in the file.
        #
        # Current problem : file doesn't seems to be updated.
        self.pipeline = gst.parse_launch(' ! '.join(['autoaudiosrc',
                                                  'queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                                                  'audioconvert',
                                                  'audioresample',
                                                  'audio/x-raw-int, rate=16000, width=16, depth=16, channels=1',
                                                  #'tee name=t',
                                                  'audioresample',
                                                  'audio/x-raw-int, rate=8000',
                                                  'vader name=vader auto-threshold=true',
                                                  'pocketsphinx lm=%s dict=%s name=listener' % (dir_path + '/pocketsphinx/lisa.lm',dir_path + '/pocketsphinx/lisa.dic'),
                                                  #'fakesink dump=1 t.']))
                                                  'valve name=valve drop=true',
                                                  #'queue',
                                                  #'wavenc',
                                                  'filesink async=0 location=' + self.recording]))

        self.vader = self.pipeline.get_by_name('vader')
        self.recording_valve = self.pipeline.get_by_name('valve')

        listener = self.pipeline.get_by_name('listener')
        listener.connect('result', self.__result__)
        listener.set_property('configured', True)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.__application_message__)

        self.pipeline.set_state(gst.STATE_PLAYING)

    def partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""

    def result(self, hyp, uttid):
        if hyp.lower() == self.botname.lower() and not self.recording_state:
            log.msg("======================")
            log.msg("%s keyword detected" % self.botname)
            self.failed = 0
            self.keyword_identified = 1
            log.msg("should play listening")
            player.play('pi-listening')
            self.listen()

    def listen(self):
        self.recording_valve.set_property('drop',False)
        self.recorder = Recorder(self,self.vader)

    def cancel_listening(self):
        log.msg("cancel_listening : player.play('pi-cancel')")
        player.play('pi-cancel')
        self.recording_state = False
        self.recording_valve.set_property('drop',True)

    # question - sound recording
    def answer(self):
        self.recording_valve.set_property('drop',True)

        print " * Contacting Google"

        """
        result = self.wit.post_speech(self.recording)
        print result
        if len(result) == 0:
            print " * nop"
            log.msg("cancel_listening : player.play('pi-cancel')")
            player.play('pi-cancel')
        else:
            print result
        """
        self.recording_state = False

    def get_pipeline(self):
        return self.pipeline

    def get_wav_file_location(self):
        return self.recording

    def __result__(self, listener, text, uttid):
        """We're inside __result__"""
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __partial_result__(self, listener, text, uttid):
        """We're inside __partial_result__"""
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __application_message__(self, bus, msg):
        msgtype =  msg.structure.get_name()
        if msgtype == 'partial_result':
            self.partial_result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'result':
            self.result(msg.structure['hyp'], msg.structure['uttid'])
