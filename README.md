# CoolMaster2
Interface between Indigo Home Automation system and Coolmaster 4000M

## User Notes

1.  This plugin has only been used with a Coolmaster4000M.  It has been used for 4 years or so with minimal issues.

1.  First thing you need is a serial connection from the Mac to the serial port on your CoolMaster Unit.  I use CoolTerm as a serial Termianl client but any will do.  
    * If using a direct connection you need a USB<-->RS@#@ adapter.  I have only found FTDI units work - rest are dodgy IMHO
    * If using a serial server (like Global Cache Itach IP2SL or WIF2SL) you can chekc the connection in CoolTerm.  Note you need the port number and IPO address like 192.168.1.88:4999
    * Connection is basic 9600 etc as outlined in PRM (programming Manual)
    * check connection by typing 'stat' (no apostrophes) and you shoudl get a status of your HVAC units

1.  Once you have a serial connection load the plugin - turn off your terminal otherwise the 2 programs will clash and may need a reboot (worst case).

1.  Once plugin is established - you can create 2 types of devices
    *   CoolMaster Controller
    *   CoolMaster HVAC Unit
    
1.  Start with the controller.  You need to niminate what type of connection (direct, Socket or Network RFC)  
    *   Direct is cable. You shoudl recognise the wacky identifier from coolterm
    *   RFC is a serial server.  Enter IP:Port
    
1.  Once controller is successfully established - you cshould see a green dot lighting and extinguishing every couple fo seconds.  This is the software polling the CoolMaster for latest info.  You will see the light is lit often and this is all thedata at 9600 taking a while.

1.  If the light stays on (sometimes the comms get locked) - restart the plugin.

1.  If the light is blinking happily - maek a new device.  The available device should list in teh HVAC units.

1.  Once you have your HVAC units created - you can make actions that corresponf to the Coolmaster commands.

1.  Once you have actions you can make control pages (I have one per zone) or interface to thermostats (mine read the Nest g thermos and set cooling heating accordingly).

1.  I have not tried this on CoolMasterNet but serial commands look similar - but there a lot more commands that may or may not be necessary.  If you have issues let me know.  Not sure if debugging is possible.

1.  The CoolMaster1000D is nearly identical to the 4000M except the addressing starts at 1 not zero.  I think the code will handle this but who knows.

1.  The serial handling was originally borrowed from the old Indigo ibraries.  Thanks to who ever wrote them.  This plugin works with 7.3 and everthing since 5.X

1.  the plugin needs pyserial which shoudl be already in your installation.

## Known Bugs

1.  If you send too many commands - they will not all get through.  This is an archive of the buffering system, the slow 9600 baud and how many devices you have (data sentence length).  Be pateint and send commands again.  Generally I haven't been inconvenienced enough to fix this so it isn't too ig a deal ti my usage.

 
