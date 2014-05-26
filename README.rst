.. image:: https://badge.waffle.io/seraf/lisa-client-linux.png?label=ready&title=Ready 
 :target: https://waffle.io/seraf/lisa-client-linux
 :alt: 'Stories in Ready'
State of the project :

.. image:: https://travis-ci.org/Seraf/LISA-CLIENT-Linux.png

Overview
########
Actually, it uses pocketsphinx to recognize the LISA keyword, then use Wit speech API (google used at backend) to recognize the sentence.
It sends the sentence to LISA Server.

Clients can be multiple (one per room for example) if needed.

To install it :

pip install lisa-client

To launch the client launch :

twistd -n lisa-client
