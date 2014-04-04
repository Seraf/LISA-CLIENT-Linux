State of the project :

.. image:: https://travis-ci.org/Seraf/LISA-CLIENT-Linux.png

Overview
########
The LISA-Client is a software which will be installed on multiple platforms.
This client will listen for a sound/voice and will transmit it to LISA-Engine.

As each platform can have his own speech to text software, the choice is your to select which engine to use.

Actually, it uses pocketsphinx to recognize the LISA keyword, then use Wit speech API (google used at backend) to recognize the sentence.
It sends the sentence to LISA Server.

Clients can be multiple (one per room for example) if needed.

To launch the client, go into the lisa directory, then launch :

twistd -ny lisa.py
