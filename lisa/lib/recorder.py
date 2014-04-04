import alsaaudio
import wave

class Loader():
    def __init__(self, end, every):
        self.end = end / every - 1
        self.every = every
        self.progress = '.'

    def _clear_line(self):
        ''' Clear one terminal line '''
        print '\x1b[1A',

    def __call__(self, i):
        ''' Print loader for the ith time '''
        if not i % self.every:
            return
        self._clear_line()
        print '[Recording]' + self.progress * (i/2) + ' ' * (self.end - (i/2)) + '[Recording]'


class Recorder:
    def __init__(self, listener, configuration):
        self.listener = listener
        open(self.listener.recordingfile, 'w').write('')
        self.configuration = configuration

        # Microphone stream config.
        self.chunk = 1024  # CHUNKS of bytes to read each time from mic
        self.channels = 1
        self.rate = 16000

        self.RECORD_SECONDS = configuration['record_seconds']
        self.SLEEP_TIME = configuration['sleep_time']

    def listen_for_speech(self):
        """
        Listens to Microphone, extracts phrases from it and sends it to
        Wit speech service
        """
        self.write_wav(self.capture_audio(Loader(self.SLEEP_TIME * self.RECORD_SECONDS, 2)))

        self.listener.answer()

    def capture_audio(self,loader):
        def setup_mic():
            inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL)
            inp.setchannels(self.channels)
            inp.setrate(self.rate)
            inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
            inp.setperiodsize(self.chunk)
            return inp

        inp = setup_mic()
        sound = []

        print "\n[*]> Starting Recording\n"
        for i in xrange(0, self.rate / self.chunk * self.RECORD_SECONDS):
            loader(i)
            _, data = inp.read()
            sound.append(data)
        print "[*]> Ready Recognize Voice\n"

        return ''.join(sound)

    def write_wav(self, data):
        wf = wave.open(self.listener.recordingfile, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(2)
        wf.setframerate(self.rate)
        wf.writeframes(data)
        wf.close()
