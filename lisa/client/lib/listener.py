# -*- coding: UTF-8 -*-

# Imports
import pygst
pygst.require('0.10')
import gobject
gobject.threads_init()
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
import gst, os
import threading
import urllib
try: # It fixes a bug with the pocketpshinx import. The first time it fails, but the second import is ok.
    import pocketsphinx
except:
    pass
import pocketsphinx
from twisted.python import log
from lisa.client.lib.speaker import Speaker
from lisa.client.lib.recorder import Recorder
from time import sleep

# Current path
PWD = os.path.dirname(os.path.abspath(__file__))


class Listener(threading.Thread):
    """
    The goal is to listen for a keyword, then it starts a voice recording
    """

    def __init__(self, lisa_client, botname, configuration):
        # Init thread class
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()

        self.botname = botname.lower()
        self.scores = []
        self.record_time_start = 0
        self.record_time_end = 0
        self.wit_thread = None
        self.loop = None
        if "keyword_score" in configuration:
            self.keyword_score = configuration['keyword_score']
        else:
            self.keyword_score = -10000

        # Build Gstreamer pipeline : mic->Pulse->tee|->queue->audioConvert->audioResample->vader->pocketsphinx->fakesink
        #                                           |->queue->audioConvert->audioResample->lamemp3enc->appsink
        self.pipeline = gst.parse_launch('pulsesrc '
                                        #+ '! ladspa-gate Threshold=-30.0 Decay=2.0 Hold=2.0 Attack=0.1 '
                                        + '! tee name=audioTee '
                                        + ' audioTee. ! queue '
                                        + '           ! audioconvert ! audioresample '
                                        + '           ! audio/x-raw-int, format=(string)S16_LE, channels=1, rate=16000 '
                                        + '           ! lamemp3enc bitrate=64 mono=true '
                                        + '           ! appsink name=app emit-signals=true '
                                        + ' audioTee. ! queue '
                                        + '           ! audioconvert ! audioresample '
                                        + '           ! vader name=vad_asr auto-threshold=true '
                                        + '           ! pocketsphinx name=asr '
                                        + '           ! fakesink async=false'
                                         )

        # Create recorder
        self.recorder = Recorder(lisa_client = lisa_client, listener = self, configuration = configuration)

        # Find client path
        if os.path.isdir('/var/lib/lisa/client/pocketsphinx'):
            client_path = '/var/lib/lisa/client/pocketsphinx'
        else:
            client_path = "%s/pocketsphinx" % PWD

        # PocketSphinx configuration
        asr = self.pipeline.get_by_name('asr')
        asr.set_property("dict", "%s/%s.dic" % (client_path, self.botname))
        asr.set_property("lm", "%s/%s.lm" % (client_path, self.botname))
        if "hmm" in configuration:
            hmm_path = "%s/%s" % (client_path, configuration["hmm"])
            if os.path.isdir(hmm_path):
                asr.set_property("hmm", hmm_path)
        asr.connect('result', self._asr_result)
        asr.set_property('configured', True)
        self.ps = pocketsphinx.Decoder(boxed=asr.get_property('decoder'))

        # Start thread
        self.start()

    def run(self):
        """
        Listener main loop
        """
        Speaker.speak("ready")
        self.pipeline.set_state(gst.STATE_PLAYING)

        # Thread loop
        self.loop = gobject.MainLoop()
        self.loop.run()

    def stop(self):
        """
        Stop listener.
        """
        Speaker.speak('lost_server')

        # Stop everything
        self.pipeline.set_state(gst.STATE_NULL)
        self.recorder.stop()
        if self.loop is not None:
            self.loop.quit()

    def _asr_result(self, asr, text, uttid):
        """
        Result from pocketsphinx : checking keyword recognition
        """
        # Check keyword detection
        if text.lower() == self.botname and self.recorder.get_running_state() == False:
            # Get scrore from decoder
            dec_text, dec_uttid, dec_score = self.ps.get_hyp()

            # Detection must have a minimal score to be valid
            if dec_score < self.keyword_score:
                log.msg("I recognized the %s keyword but I think it's a false positive according the %s score" % (self.botname, dec_score))
                return

            # Logs
            self.scores.append(dec_score)
            log.msg("======================")
            log.msg("%s keyword detected" % self.botname)
            log.msg("score: {} (min {}, moy {}, max {})".format(dec_score, min(self.scores), sum(self.scores) / len(self.scores), max(self.scores)))

            # Start voice recording
            Speaker.speak('yes')

            # Start recorder
            self.recorder.set_running_state(True)

    def get_pipeline(self):
        """
        Return Gstreamer pipeline
        """
        return self.pipeline
