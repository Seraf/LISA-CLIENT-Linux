# -*- coding: UTF-8 -*-

# Imports
from lisa.client.ConfigManager import ConfigManagerSingleton
from collections import deque
import threading
from wit import Wit
import time
from time import sleep
from twisted.python import log
from lisa.client.lib.speaker import Speaker

class Recorder(threading.Thread):
    def __init__(self, lisa_client, listener):
        # Init thread class
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()

        self.lisa_client = lisa_client
        self.configuration = ConfigManagerSingleton.get().getConfiguration()
        self.pipeline = listener.get_pipeline()
        self.capture_buffers = deque([])
        self.running_state = False
        self.wit = Wit(self.configuration['wit_token'])
        self.record_time_start = 0
        self.record_time_end = 0

        # Get app sink
        self.rec_sink = self.pipeline.get_by_name('rec_sink')
        self.rec_sink.connect('new-buffer', self._capture_audio_buffer)

        # Configure vader
        # Using vader on pocketsphinx branch and not a vader on record branch,
        # because vader forces stream to 8KHz, so record quality would be worst
        vader = self.pipeline.get_by_name('vad_asr')
        vader.connect('vader-start', self._vader_start)
        vader.connect('vader-stop', self._vader_stop)

        # Get elements to connect/disconnect pockesphinx during record
        self.asr_tee = self.pipeline.get_by_name('asr_tee')
        self.asr_sink = self.pipeline.get_by_name('asr_sink')
        self.asr = self.pipeline.get_by_name('asr')
        self.asr_tee.unlink(self.asr_sink)

        # Start thread
        self.start()

    def stop(self):
        # Raise stop event
        self.running_state = False
        self._stopevent.set()

    def get_running_state(self):
        """
        Is the recorder recording?
        """
        return self.running_state

    def set_running_state(self, running):
        """
        Start/Stop a voice record
        """
        if running == True and self.running_state == False:
            self.running_state = True

            # Disconnect pocketsphinx from pipeline
            self.asr_tee.link(self.asr_sink)
            self.asr_tee.unlink(self.asr)

        elif running == True and self.running_state == True:
            self.running_state = False

    def run(self):
        """
        Recorder main loop
        """
        CONTENT_TYPE = 'audio/mpeg3'
        result = ""
        retry = 1

        # Thread loop
        while not self._stopevent.isSet():
            # Wait record order
            if self.running_state == False:
                sleep(.1)
                continue

            # Activate capture, wait for 3s of silence before cancelling
            self.record_time_start = 0
            self.record_time_end = time.time() + 3
            self.capture_buffers.clear()
            result = ""
            print "\n"

            # Send captured voice to wit
            try:
                result = self.wit.post_speech(data = self._read_audio_buffer(), content_type=CONTENT_TYPE)
            except:
                # On error
                if self.running_state == True:
                    log.err("Wit exception")

                # No retry when no sound recorded
                if self.record_time_start == 0:
                    retry = 0

            # If record was stopped during recording
            if self.running_state == True:
                # If Wit returned an error
                if len(result) == 0:
                    if retry != 0:
                        Speaker.speak('not_understood')

                # Send recognized text to the server
                else:
                    self.lisa_client.sendMessage(message=result['msg_body'], type='chat', dict=result['outcome'])
                    retry = 0

            # If no more retry
            if retry == 0:
                # Reset state
                self.running_state = False
                retry = 1

                # Reconnect pocketsphinx to pipeline
                self.asr_tee.link(self.asr)
                self.asr_tee.unlink(self.asr_sink)
            else:
                # Decrement retries
                retry = retry - 1

    def _vader_start(self, ob, message):
        """
        Vader start detection
        """
        # Reset max recording time
        if self.running_state == True:
            if self.record_time_start == 0:
                self.record_time_start = time.time()
                self.record_time_end = self.record_time_start + 10

    def _vader_stop(self, ob, message):
        """
        Vader stop detection
        """
        # Stop recording if no new sentence in next 2s
        if self.running_state == True:
            if self.record_time_start != 0 and self.record_time_end > time.time() + 2:
                self.record_time_end = time.time() + 2

    def _capture_audio_buffer(self, app):
        """
        Gstreamer pipeline callback : Audio buffer capture
        """
        # Get buffer
        Buffer = self.rec_sink.emit('pull-buffer')

        # If recording is running
        if self.running_state == True:
            if self.record_time_start == 0:
                # Start was not called by vader
                self._vader_start(ob = None, message = None)

            # Add buffer to queue
            self.capture_buffers.append(Buffer)

    def _read_audio_buffer(self):
        """
        Read buffers from capture queue
        """
        last_progress = -1

        # While recording is running
        while time.time() < self.record_time_end:
            # If there is a captured buffer
            if len(self.capture_buffers) > 0:
                data = self.capture_buffers.popleft()
                yield data
            else:
                # Wait another buffer
                sleep(.05)

            # Print progression
            if self.record_time_start != 0:
                progress = (int)(2 * (time.time() - self.record_time_start)) + 1
            else:
                progress = 0
            if last_progress != progress:
                last_progress = progress
                print '\x1b[1A',
                print '[Recording]' + '.' * progress + ' ' * (20 - progress) + '[Recording]'

        print "> Ready Recognize Voice\n"
