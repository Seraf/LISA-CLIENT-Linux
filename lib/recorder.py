import os

import pygtk
pygtk.require('2.0')
import gobject
import pygst
pygst.require('0.10')
gobject.threads_init()
import gst


class Recorder:
    def __init__(self, listener,vader):
        self.listener = listener
        self.started = False
        self.finished = False

        self.pipeline = self.listener.get_pipeline()
        self.recording = self.listener.get_wav_file_location()

        vader.connect('vader_start', self.__start__)
        vader.connect('vader_stop', self.__stop__)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.__application_message__)

        print " * Listening closely..."
        self.listener.recording_state = True
        gobject.timeout_add_seconds(5, self.cancel)
        self.start()

    def start(self):
        self.started = True
        print " * Recording..."

    def stop(self):
        print " # stop_now"
        print " * Stored recording to ", self.recording
        print " * Done."
        self.finished = True
        self.listener.answer()

    def cancel(self):
        print " # cancel", self.finished, self.started
        if self.finished:
            print " # cancel - noop"
            return

        if not self.started:
            self.finished = True
            print " * Not a word in the past 5 seconds, cancelling"
            #self.pipeline.set_state(gst.STATE_NULL)
            #self.recorder.set_state(gst.STATE_NULL)
            self.listener.cancel_listening()

    def __start__(self, vader, arg0):
        if not self.finished:
            print " # vader:start"
            struct = gst.Structure('vader_start')
            struct.set_value('arg0', arg0)
            vader.post_message(gst.message_new_application(vader, struct))

    def __stop__(self, vader, arg0):
        if not self.finished:
            print " # vader:stop"
            struct = gst.Structure('vader_stop')
            struct.set_value('arg0', arg0)
            vader.post_message(gst.message_new_application(vader, struct))

    def __application_message__(self, bus, msg):
        msgtype = msg.structure.get_name()
        if self.finished:
            return
        if msgtype == 'vader_stop':
            self.stop()
        elif msgtype == 'vader_start':
            self.start()