try:
    import sphinxbase
    import pocketsphinx
except:
    pass
import pocketsphinx
from wit import Wit
import gobject
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
from twisted.python import log
import json, os
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst
from lisa.client.lib import player
from lisa.client.lib.recorder import Recorder


path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
if os.path.exists('/etc/lisa/client/configuration/lisa.json'):
    configuration = json.load(open('/etc/lisa/client/configuration/lisa.json'))
else:
    configuration = json.load(open(os.path.normpath(dir_path + '/../' + 'configuration/lisa.json')))


class Listener:
    def __init__(self, lisaclient, botname):

        self.configuration = configuration
        self.recordingfile = '/tmp/google.wav'
        self.recording_state = False
        self.botname = botname
        self.lisaclient = lisaclient
        self.failed = 0
        self.keyword_identified = 0
        self.recorder = Recorder(listener=self,configuration=self.configuration)
        self.wit = Wit(self.configuration['wit_token'])

        # The goal is to listen for a keyword. When I have this keyword, I open the valve and the voice is recorded
        # to the file. Then I submit this file to google/wit, and drop again the flow to not write in the file.
        #
        # Current problem : file doesn't seems to be updated.

        self.pipeline = gst.parse_launch('alsasrc ! audioconvert ! audioresample '
				+ '! vader name=vad auto-threshold=true '
				+ '! pocketsphinx name=asr ! fakesink')

        self.vader = self.pipeline.get_by_name('vad')

        asr = self.pipeline.get_by_name('asr')
        if os.path.isfile('/var/lib/lisa/client/pocketsphinx/lisa.dic'):
            asr.set_property("dict", '/var/lib/lisa/client/pocketsphinx/lisa.dic')
            asr.set_property("lm", '/var/lib/lisa/client/pocketsphinx/lisa.lm')
        else:
            asr.set_property("dict", "%s/lib/pocketsphinx/lisa.dic" % os.path.normpath(dir_path + '/../'))
            asr.set_property("lm", "%s/lib/pocketsphinx/lisa.lm" % os.path.normpath(dir_path + '/../'))
        asr.connect('result', self.__result__)
        asr.set_property('configured', True)

        self.ps = pocketsphinx.Decoder(boxed=asr.get_property('decoder'))

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.__application_message__)

        self.pipeline.set_state(gst.STATE_PLAYING)

    def partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""

    def result(self, hyp, uttid):
        if hyp.lower() == self.botname.lower() and not self.recording_state:
            struct = gst.Structure('result')
            dec_text, dec_uttid, dec_score = self.ps.get_hyp()

            if dec_score >= self.configuration['keyword_score']:
                log.msg("======================")
                log.msg("%s keyword detected" % self.botname)
                log.msg("score: {}".format(dec_score))

                self.failed = 0
                self.keyword_identified = 1
                self.record()
            else:
                log.msg("I recognized the %s keyword but I think it's a false positive according the %s score" %
                        (self.botname.lower(), dec_score))

    def cancel_listening(self):
        log.msg("cancel_listening : player.play('pi-cancel')")
        player.play('pi-cancel')
        self.recording_state = False

    # sound recording
    def record(self):
        self.pipeline.set_state(gst.STATE_PAUSED)
        self.recording_state = True
        # This content type (raw) allow to send data from mic directly to Wit and stream chunks
        # thanks to the generator
        CONTENT_TYPE = 'raw;encoding=signed-integer;bits=16;rate=16000;endian=little'
        result = self.wit.post_speech(data=self.recorder.capture_audio(), content_type=CONTENT_TYPE)
        player.play('pi-cancel')
        log.msg(" * Contacting Google")
        if len(result) == 0:
            log.msg("cancel_listening : player.play('pi-cancel')")
            player.play('pi-cancel')
        else:
            log.msg(result)
            self.lisaclient.sendMessage(result['msg_body'])
        self.recording_state = False
        self.pipeline.set_state(gst.STATE_PLAYING)

    def get_pipeline(self):
        return self.pipeline

    def get_wav_file_location(self):
        return self.recordingfile

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