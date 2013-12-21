.. _configuration:

Configuration
=============

LISA
----
In the configuration/lisa.json file, you will find parameters to replace according your needs.

**lisa_url**: You can setup in this field a dns or an ip, pointing to your LISA Server.

**lisa_engine_port**: This is the communication port you have setup on the LISA Server. By default the value is 10042.

**lisa_engine_port_ssl**: This is the secure communication port you have setup on the LISA Server. By default the value is  10043.

**enable_secure_mode**: This value define if the client should connect to the server with SSL or not. By default the value is false.

**debug_input**: If this value is true, all data received will be displayed on the stdout or logged in a file. By default this value is true.

**debug_output**: If this value is true, all data sent will be displayed on the stdout or logged in a file. By default this value is true.

**zone**: Define the zone where is located the client. By default this value is "zone1". There can be more than one client per zone.

**tts**: You can setup the module that will be used by speech-dispatcher here.

**lang**: This is the language the tts will use.
