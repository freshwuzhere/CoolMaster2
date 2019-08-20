import os
import sys
import serial
import time
import functools
import threading
import string

import indigo

from hvac_params import hvac_params


######
#   CoolMaster is a responder only and does not issue unsolicited messages except at startup
#  	This behaviour is different to many other indigo plugin serial devices
#####

######
#  Debug logging will generate a lot of lines in log files - careful!
#####

#####
# 1 sec seems like a balanced sleep after commands between
# the USB-to-Serial and Aqualink Serial RS connection.  It's slooooow.
#####

#######################
## CoolMaster state structure to hand around
#######################


#####
# make a list of known commands to check against
####

kKnownCommands=["alloff","allon","cool","dry","heat","auto","fan","fspeed","off","on","set","stat3","swing","temp","group"]

class CoolMaster(object):
	coolMasterUnitParams = []
	kSleepAfterSerialCommand = 0.5
	kSleepBetweenSerialLoop = 3
	kCyclesBetweenHVACCheck = 2
	kSerialPortBaud = 9600
	#  this means 2 stat3 will be called on cycle 0 and 4 (2 between) set to zero if you want to detect changes more quickly.
	# this is how room temp feeds back to the system.
	# tis is the system temperature expectations - ie - if everything is in F - then enter F
	kCMTempUnits = "F"
	kIndigoTempUnits = "F"


	kTempConvertCM2I = kCMTempUnits + "2" + kIndigoTempUnits
	kTempConvertI2CM =   kIndigoTempUnits + "2" + kCMTempUnits




	##############################################################################################
	def __init__(self, plugin):
		self.plugin = plugin

	########################################
	def __del__(self):
		pass

	##############################################################################################
	def startCommThread(self, dev):



		###   old local serial

		####self.plugin.debugLog("\n############## \ndevProps  = " + str(devProps)  + " \n ################\n")
		####portName = devProps.get("devicePort")
		####self.plugin.debugLog("Serial Port Name is " + portName)
		##	self.conn = self.plugin.openSerial(dev.name, portName, 9600, timeout=1, writeTimeout=1)
		###

		# get the serial port ID from the query

		showErrors = (len(dev.errorState) == 0)		# only show/log errors if this is the first failure
		errorLogFunc = self.plugin.errorLog
		if not showErrors:
			errorLogFunc = self.plugin.debugLog



		devProps = dev.pluginProps
		self.plugin.debugLog("\n############## \ndevProps  = " + str(devProps)  + " \n ################\n")


		#  from easy daq - use existing dev Props  devProps = self.easydaq.calcNormalizedProps(dev)

		serialUrl = self.plugin.getSerialPortUrl(devProps, u"devicePort")

		self.plugin.debugLog("Serial Port Name is " + serialUrl)
		try:
			self.conn = self.plugin.openSerial(dev.name, serialUrl, self.kSerialPortBaud, timeout=1, writeTimeout=1, errorLogFunc=errorLogFunc)
		except Exception , e :
			self.plugin.debugLog("EXCEPTION " + str(e))
			self.plugin.errorLog("EXCEPTION " + str(e))
			self.plugin.exceptionLog()


		### If connection to serial device is successfully statrted, queue initial commands
		### Else, log error starting communication
		if self.conn:
			self.plugin.debugLog("Device name is " + dev.name)

			self.commQueue = []
			for command in self.commQueue:
				self.plugin.debugLog("In queue: " + command)

			### Start separate concurrentSerialComm thread - syntax roughly based on EasyDAQ Plugin
			devId = dev.id
			self.concurThread = threading.Thread(target=functools.partial(self.concurrentSerialComm, devId))
			self.concurThread.start()
			self.plugin.debugLog("Started concurrent thread.")

		else:
			indigo.server.log("Error initializing communciations with serial device " + dev.name)

	######################
	# Send command to stop concurrentSerialComm thread, then close serial connection and exit.
	def stopCommThread(self, dev):
		self.plugin.debugLog("Initiating stop of concurrent thread.")
		self.queueSerialCmd("stopConcurrentSerialComm")
		time.sleep(3)		# Give plenty of time for command to stop concurrent thread to execute.
		try:
			self.conn.close()
		except Exception , e :
			self.plugin.debugLog("EXCEPTION " + str(e))
			self.plugin.errorLog("EXCEPTION " + str(e))
			self.plugin.exceptionLog()


		self.plugin.debugLog("closed connection to device " + dev.name)


	##############################################################################################
	def concurrentSerialComm(self, devId):
		try:
			counter = 0
			self.plugin.debugLog("Starting concurrent serial communications.")
			while True:
				##################################################################################
				# First on each pass, get current device state infomation, as it may have changed,
				# 	and needs to be used to ensure proper commands for some state updates.
				dev = indigo.devices[devId]
				##################################################################################
				# Next, on each pass read/decode any data sitting in the buffer - unlikely to have anything here
				# but best to clear it out before geting more stuff on top
				success = self.readSerialBuffer(devId)
#				self.plugin.debugLog("Reading serial buffer complete - found this" )

				##################################################################################
				# Next, send commands from those queued.
				# Use a copy of the queue to avoid confusion if added to while executing.
				# Check for command to terminate thread
				# Clear commands executed here, but not any added while executing.
				# Only allow temperature requsts if pump is on (all systems) and valves are in proper position (Combo systems).
				# Note that user could send other commands that are not allowed,
				if len(self.commQueue) >= 1:
					self.plugin.debugLog("Queue has " + str(len(self.commQueue)) + " command(s) waiting.")
					workingQueue = self.commQueue
					if "stopConcurrentSerialComm" in workingQueue:	# Command to stop queue?
						self.plugin.errorLog("Raising exception to stop concurrent thread.")
						workingQueue = []
						self.commQueue = []			#Clear queue
						raise self.StopThread		# Raise exception to stop thread.
					lenQueue = len(workingQueue)
					self.plugin.debugLog("length of queue = " + str(lenQueue))
					for command in workingQueue:
						self.plugin.debugLog("Processing command: " + command)
						self.sendSerialCmd(devId, command)
						self.plugin.debugLog(command + " command completed.")

					self.commQueue = self.commQueue[lenQueue:]

				##################################################################################
					# Sleep a bit on each cycle.
					# then read the buffer - wait enough time for device to repsond.  then re-start cycle waiting for command
					self.plugin.debugLog("about to sleep")
					time.sleep(self.kSleepAfterSerialCommand)
					success = self.readSerialBuffer(devId)
					self.plugin.debugLog("SUCCESS in read serial  =  ") # + str(success))
#					self.plugin.debugLog("dev status at critical juncture \n#####################################\n" + str(dev))

				time.sleep(self.kSleepBetweenSerialLoop)  # gap between loops waiting for a command
#				self.plugin.debugLog("dev status at critical juncture \n#####################################\n" + str(dev))
				###############
				##### check to see if status update required - if so - run this routine
				###############
				self.plugin.debugLog("Counter = " + str(counter))
				if counter > self.kCyclesBetweenHVACCheck:
					self.queueSerialCmd("stat3")
					counter=0
				else:
					counter = counter +1
				self.plugin.debugLog("End of Routine cycle through concurrentSerialComm thread.")

		### Exceptions to exit thread.  !!! Need to understand 2nd and 3rd except:, "borrowed" from EasyDAQ plugin.
		except self.StopThread:
			self.plugin.debugLog("Quiet Stop  ")
			pass	# silently fall into finally: section below
		except Exception, e:
			self.plugin.debugLog("EXCEPTION " + str(e))
			self.plugin.exceptionLog()
		except:
			self.plugin.debugLog("EXCEPTION ")
			self.plugin.exceptionLog()
		finally:
			self.plugin.debugLog("Should now stop concurrent thread.")
			pass	# Finally, exit thread.


	##############################################################################################
	### Add new command to queue, which is polled and emptied by concurrentSerialComm funtion
	def queueSerialCmd(self, command):
		self.plugin.debugLog("\nIN QUEUESERIALCMD "  + command)
		self.commQueue.append(command)	# Append new command.
		self.plugin.debugLog("\n EXITING  QUEUESERIALCMD "  + command)


	########################################
	### Send queued command to CoolMaster, then read reply.
	def sendSerialCmd(self, devId, command):
		dev = indigo.devices[devId]
#		self.plugin.debugLog(" \nIN sendSERIALCMD --" + command)
		writeCommand = command + "\r\r\n"	# append carraige return
		dev.updateStateOnServer("commActive", value=True , uiValue = u"True")
		sentCount = self.conn.write(writeCommand)
		dev.updateStateOnServer("commActive", value=False, uiValue = u"False")

	##############################################################################################
	### Check to see if any new data on serial read - unlikely
	def readSerialBuffer(self, devId):
		try:
			dev = indigo.devices[devId]
#			self.plugin.debugLog("in read Serial Buffer ")
		###loop on line reader to get the full response string
			success = "false"
			buffCount = 999
			responseLineString = ""
			responseList = []
			while buffCount > 0 :
				dev.updateStateOnServer("commActive", value=True, uiValue = u"True")
				responseLineString = self.conn.readline()
				dev.updateStateOnServer("commActive", value=False, uiValue = u"False")
				buffCount = len(responseLineString)

				if buffCount > 0:
					responseList.append(responseLineString)
			responseLength = len(responseList)
#			self.plugin.debugLog("Number of lines read is " + str(responseLength) + "\n" + str(responseList))
			if responseLength > 0:
#				self.plugin.debugLog("decoding ")
				try:
					success = self.decodeResponse(devId, responseList)
					self.plugin.debugLog("DECODE SUCCESS = " + str(success))
					if success == "SUCCESS" :
						self.plugin.debugLog("about to setStates ")
						success = self.setStatesFromProps(devId)
						self.plugin.debugLog("STATE SET SUCCESS = " + str(success))

				except:
					self.plugin.errorLog("failed teh decode Response")


#			time.sleep(self.kSleepAfterSerialCommand)
#			self.plugin.debugLog("returning =  " + str(success))
			return (success)
		except:
			self.plugin.debugLog("failed in read serial buffer at top.")


	##############################################################################################
	### Decode response
	### This is a simpel read and update the correct data then set states of the thermostat devices
	def decodeResponse(self, devId, responseList):
#		self.plugin.debugLog("in decode ")
		dev = indigo.devices[devId]
		responseLength = len(responseList)
#		self.plugin.debugLog("List length = " + str(responseLength)  + "\n"  + str(responseList))
#		self.lineDecodeUpdateProperties( devId ,"test test test test test test test test" )
		#
		#	first delete the old properties
		#
# 		origLocalProps = dev.pluginProps
#
#  		dev.replacePluginPropsOnServer(None)
#
# 		newLocalProps = dev.pluginProps
#
#  		self.plugin.debugLog("###### ____ ###### \n ###    new props prior to loading =  " + str(newLocalProps) + "\n######______#######")
#
# 		for k in origLocalProps.keys() :
#  			if str(k).startswith("HVAC"):
#  				self.plugin.debugLog("HVAC delete " +str(origLocalProps[str(k)]))
# # 				pass
#  			else:
#  				self.plugin.debugLog("KEEP HVAC yes Copy "  + str(origLocalProps[str(k)]))
#  				newLocalProps.update({(str(k)):origLocalProps[str(k)],"checkForUpdates":True})
# # 				pass
# #
# #
#  		self.plugin.debugLog("###### ____ ###### \n ###    new props =  " + str(newLocalProps) + "\n######______#######")
#  		dev.replacePluginPropsOnServer(newLocalProps)
#
		localProps = dev.pluginProps

 		self.plugin.debugLog("###### ____ ###### \n ###    new props prior to deleting =  " + str(localProps) + "\n######______#######")

		for k in localProps.keys() :
 			if str(k).startswith("HVAC"):
# 				self.plugin.debugLog("HVAC delete " +str(localProps[str(k)]))
 				del localProps[str(k)]
# 				pass
 			else:
# 				self.plugin.debugLog("KEEP HVAC yes Copy "  + str(localProps[str(k)]))
 				pass
#
#
# 		self.plugin.debugLog("###### ____ ###### \n ###    new props after trim before loading =  " + str(localProps) + "\n######______#######")
 		dev.replacePluginPropsOnServer(localProps)

		try:

			for line in responseList :

				self.plugin.debugLog("decoding Line: " + line )
				### Now go through the possible responses.

				if line[0] == "0" :
					self.plugin.debugLog("its a data line! going to decode"  )
					###we have a response - send ot to parser"
					self.lineDecodeUpdateProperties( devId ,line )
					retValue = "DATA_READ"
#					self.plugin.debugLog("line decoded " + retValue )

				elif line[0] == ">" :
					### FILL
#					self.plugin.debugLog("reading an arrow " )
					pass

				elif line[0:2] == "OK"   :
					### success on Comms return now if we have data
					if retValue == "DATA_READ" :
						retValue = "SUCCESS"
					else :
						retValue = "EMPTY"

				elif line[0:3] == "Bad"	:
					### something bad in command
					retValue = "FAIL BAD PARAMS INPUT"
#					self.plugin.debugLog("bad params = " + retValue)

				elif line[0:7] == "Unknown" :
					### command not recognised
					retValue = "FAIL UNKNOWN COMMAND"
#					self.plugin.debugLog("unkown = " + retValue)

				else:
					retValue = "FAIL NOTHING RECOGNISED"

#			self.plugin.debugLog("end trap --> return value = " + retValue)
	#		self.plugin.debugLog("###### ____ ###### \n ###    after update =  " + str(localProps) + "\n######______#######")
		except:
			retValue = "Epic Fail"
			self.plugin.debugLog("BAD  End trap --> return value = " + retValue)

		finally:
			return (retValue)



	def lineDecodeUpdateProperties(self, devId, line_in):  # note devId is the Controller - we need to find the  HVAC unit
		####
		#	This tokenises the response (so no need to worry about which column is where)
		#	then writes to Properties associated directly with the name - decode and encoded
		#	so CoooMaster device 001 will become HVAC_001 and the following properties are saved
		#	in a string - dictionary  HVAC_001
		#	HVAC_001_ID 	: "001"
		#	HVAC_001_ON_OFF : 'ON' or 'OFF'
		# 	HVAC_001_SET_T 	: 'XXXF'   string
		#	HVAC_001_ROOM_T	: 'XXXF'	string
		#	HVAC_001_FAN_S	: 'High' string
		#	HVAC_001_OP_MODE: 'Cool' string
		#	HVAC_001_STATUS	: 'OK'  or Error Code string
		#	HVAC_001_FILTER	: '0' or '1'	filter status
		###
		try:
			self.plugin.debugLog("in line decoder  = " + line_in + str(devId))
			dev= indigo.devices[devId]
			localProps = dev.pluginProps
			tokenList = line_in.split()
			self.plugin.debugLog("tokenList  = " + str(tokenList))
			# write the props required to the devId (the controller)

			# Forst get local copy
			localProps = dev.pluginProps

			#now make the dict name

	#		self.plugin.debugLog("tokenList[0] = " + tokenList[0])
	#		self.plugin.debugLog("length tokenList = " + str(len(tokenList)))
			unit_pre_name = "HVAC_" + tokenList[0] + "_"

#			self.plugin.debugLog("unit name = " + unit_pre_name + " --- Length of List = "  + str(len(tokenList)))

			if len(tokenList) == 8 :
				localProps.update({str(unit_pre_name+"ID"):tokenList[0]})
				localProps.update({str(unit_pre_name+"ON_OFF"):tokenList[1]})
				localProps.update({str(unit_pre_name+"SET_T"):self.decodeTempString(tokenList[2])})
				localProps.update({str(unit_pre_name+"ROOM_T"):self.decodeTempString(tokenList[3])})
				localProps.update({str(unit_pre_name+"FAN_S"):tokenList[4]})
				localProps.update({str(unit_pre_name+"OP_MODE"):tokenList[5]})
				localProps.update({str(unit_pre_name+"STATUS"):tokenList[6]})
				localProps.update({str(unit_pre_name+"FILTER"):int(tokenList[7])})
				dev.replacePluginPropsOnServer(localProps)

			else:
				self.plugin.errorLog("incorrect variable count in Decode CM  -- Token List length = " + str(len(tokenList)))
				return


	#		self.plugin.debugLog("props afetr replace \n  ######################### = " + str(dev.pluginProps))
		except:
			self.plugin.debugLog("BUSTED - lin decoder")
		return

	#########
	#
	#THIS DECODE STRING DATA READ FROM 073F TO NUMBER 73
	#
	#########

	def decodeTempString(self, str_val):
		current_temp = int(str_val[:3])
		check_FC = str_val[-1:]
		return current_temp

#####################################
#
#	This routine counts the number of units online at present.
#   currently looks at the
#
#########



###########################################################################
##  coolMaster routines
##########

	def coolMasterIndigoDictCreate(self , devId, UnitParams):
#		self.plugin.debugLog("IN PROP SET" + str(devId) + str(UnitParams))
		dev = indigo.devices[devId]
		#self.plugin.debugLog("GOT DEV" + str(devId) + str(dev))
		# First update Deice Properties
		localPProps = dev.pluginProps
#		self.plugin.debugLog("LOCAL PROPS COPY \n" + str(localPProps))
		#unitList = indigo.List()
		unitList = list()
		for unit in UnitParams:
			unitList.append("A_"+unit.address)

#		self.plugin.debugLog("HERE IS UNIT LIST " + str(unitList))


		try:
#			self.plugin.debugLog(" in if statement ")
			localPProps.update({"HVACList":unitList,"checkForUpdates":True})
		except KeyError :
			self.plugin.debugLog(" in excpetion ")
			pass

#		self.plugin.debugLog(" after if statement ")

		unitCount = len(UnitParams)
#		self.plugin.debugLog("unit count =  "  + str(unitCount))
		localPProps.update({"units":unitCount,"checkForUpdates":True})

		dev.replacePluginPropsOnServer(localPProps)
#		self.plugin.debugLog("\n##########\n####DEV with NEW PROPS\n######### " + str(dev))


	def testComms(self,dev):
		devId = dev.id
		self.plugin.debugLog("\n############\n### ABOUT TO TEST STAT3 \n#############\n")
# 		self.queueSerialCmd("stat3")
# 		time.sleep(4)
# 		success = self.coolmaster.readSerialBuffer(devId)
#		self.plugin.debugLog("\n############\n### output HVAC Unit PArams : = " + str(self.coolmaster.coolMasterUnitParams) + "\n#############\n")

		return (True)

#################################
#
#	This takes the device Id to get the Properties stored
#	From these it steps through the HVAC units that were read and sets the parameter
#	Lastly it checks if there are HVAC units that were not read (ie dropped of the M-NET)
#	AND checks which HVACS are on the M-NET and not configured yet.
#
#################################

	def setStatesFromProps(self,devId):
#		self.plugin.debugLog("In setStates")
		CM_dev = indigo.devices[devId]
#		self.plugin.debugLog("\n##########\nCM_dev device = \n" + str(CM_dev) + "\n###########")
		retValue = "waiting to be set"
		####
		#	Get each HVAC UNIT - decode it's props to see it's name and then
		#	read each parameter from the Props and set the states
		####

		for HVAC_dev in indigo.devices.iter("self"):
			if HVAC_dev.deviceTypeId == "HVAC_Unit_CM":
#				self.plugin.debugLog("HVAC_Name = "  + str(HVAC_dev.name)  + " \n HVAC DEV PROPRS = " + str(HVAC_dev))
				HVAC_Id = HVAC_dev.pluginProps["ACDevices"]
#				self.plugin.debugLog("HVAC_Id = " + str(HVAC_Id))
				HVAC_Name = "HVAC_" + HVAC_Id + "_"
				HVAC_temp = HVAC_Name + "ID"
#				self.plugin.debugLog("HVAC_Name = "  + HVAC_Name + " HVAC _ ID =  " + str(HVAC_Id)  + "temp " + str(HVAC_temp))


			# 	First test that the CM has Props for this device - if not warn the user
				if HVAC_temp in CM_dev.pluginProps.keys():
#					self.plugin.debugLog("In the set LOOP")
					HVAC_dev.updateStateOnServer("power", value=CM_dev.pluginProps[str(HVAC_Name+"ON_OFF")])
					HVAC_dev.updateStateOnServer("setPoint", value=CM_dev.pluginProps[str(HVAC_Name+"SET_T")])
					HVAC_dev.updateStateOnServer("roomTemperature", value=CM_dev.pluginProps[str(HVAC_Name+"ROOM_T")])
					HVAC_dev.updateStateOnServer("fanSpeed", value=CM_dev.pluginProps[str(HVAC_Name+"FAN_S")])
					HVAC_dev.updateStateOnServer("mode", value=CM_dev.pluginProps[str(HVAC_Name+"OP_MODE")])
					HVAC_dev.updateStateOnServer("status", value=CM_dev.pluginProps[str(HVAC_Name+"STATUS")])
					HVAC_dev.updateStateOnServer("filter", value=CM_dev.pluginProps[str(HVAC_Name+"FILTER")])
					self.plugin.debugLog("End of the set LOOP DEV = " + str(HVAC_dev))
					retValue = "SUCCESS"
				else:
					self.plugin.erorLog("HVAC_Device -->" +HVAC_Dev.name + "   --- >NOT IN LATEST SERIAL READ FROM COOMASTER")
					retValue = "FAIL"

		return(retValue)


	def setMode(self , dev, newMode):
		# decode which unit so we can address appropriately
		localProps = dev.pluginProps
		if "ACDevices" in localProps:
			address =  localProps["ACDevices"]

			self.plugin.debugLog("#####  IN handle CHANGE HVAC MODE ACTION ###  address of unit is " + address )

		else:
			self.plugin.debugLog("#####  ACDEvise not in Plugin Props " + str(localProps) )
			return()

		# decode hvac mode into command mode for coolmaster
		if newMode == "Off":
			command_str = "off "+ address +  "\r"
			dev.updateStateOnServer("power", value="OFF")

		elif newMode == "On":
			command_str = "on " + address +  "\r"
			dev.updateStateOnServer("power", value="ON" )

		elif newMode == "AllOn":
			command_str = "allon " +  "\r"
			dev.updateStateOnServer("power", value="ON" )

		elif newMode == "AllOff":
			command_str = "alloff " +  "\r"
			dev.updateStateOnServer("power", value="OFF" )

		elif newMode == "Heat":
#			command_str = "on " + address +  "\r" +  "heat "+ address +  "\r"
			command_str = "heat "+ address +  "\r"
			dev.updateStateOnServer("mode", value="Heat" , uiValue = "heat")
			dev.updateStateOnServer("power", value="ON" )


		elif newMode == "Cool":
#			command_str = "on " + address +  "\r" +"cool "+ address +  "\r"
			command_str = "cool "+ address +  "\r"
			dev.updateStateOnServer("mode", value="Cool" , uiValue="cool")
			dev.updateStateOnServer("mode", value="Cool" , uiValue="cool")
			dev.updateStateOnServer("power", value="ON" )

		elif newMode == "Auto":
#			command_str = "on " + address +  "\r" + "auto "+ address +  "\r"
			command_str =  "auto "+ address +  "\r"
			dev.updateStateOnServer("mode", value="Auto" , uiValue= "auto")
			dev.updateStateOnServer("power", value="ON" )

		elif newMode == "Dry":
#			command_str = "on " + address +  "\r" + "dry "+ address +  "\r"
			command_str = "dry "+ address +  "\r"
			dev.updateStateOnServer("mode", value="Dry" , uiValue = "dry")
			dev.updateStateOnServer("power", value="ON" )

		elif newMode == "Fan":
			command_str =  "fan "+ address +  "\r"
#			command_str = "on " + address +  "\r" + "fan "+ address +  "\r"
			dev.updateStateOnServer("mode", value="Fan" , uiValue = "fan")
			dev.updateStateOnServer("power", value="ON" )

		else :
			self.plugin.debugLog("Couldn't decode HVAC mode change HVAC address" + address  + "Mode call was" + newMode)

		self.plugin.debugLog("Command String = " + command_str )
		self.queueSerialCmd(command_str)


	def setFanMode(self, dev, newFanMode ):
		localProps = dev.pluginProps
		if "ACDevices" in localProps:
			address =  localProps["ACDevices"]

			self.plugin.debugLog("#####  IN handle CHANGE FAN MODE ACTION ###  address of unit is " + address )

		else:
			self.plugin.debugLog("#####  AC DEvise not in Plugin Props " + str(localProps) )
			return()

		# decode hvac mode into command mode for coolmaster
		if newFanMode == "Auto":
			command_str = "fspeed "+ address + " a" +  "\r"
			dev.updateStateOnServer("fanSpeed", value="Auto")

		elif newFanMode == "Top":
			command_str = "fspeed "+ address + " t" +  "\r"
			dev.updateStateOnServer("fanSpeed", value="Top")

		elif newFanMode == "High":
			command_str = "fspeed "+ address + " h" +  "\r"
			dev.updateStateOnServer("fanSpeed", value="High")

		elif newFanMode == "Med":
			command_str = "fspeed "+ address + " m" +  "\r"
			dev.updateStateOnServer("fanSpeed", value="Med")

		elif newFanMode == "Low":
			command_str = "fspeed "+ address + " l" +  "\r"
			dev.updateStateOnServer("fanSpeed", value="Low")

		else :
			command_str = "\r"
			self.plugin.debugLog("Command not Recognised = " + newFanMode )

		self.plugin.debugLog("Command String = " + command_str )
		self.queueSerialCmd(command_str)

		return()

	def setTemp(self,dev,newSetPoint):
		self.plugin.debugLog("setpoint received = " + str(newSetPoint))
		if newSetPoint >-2 and newSetPoint < 95:  # sanity check
			address = dev.pluginProps["ACDevices"]
			command_str = "temp "+ address + " " + str(newSetPoint)  +  "\r"
		else:
			self.plugin.debugLog("temperature outsoide range = " + str(newSetPoint))
			return

		self.plugin.debugLog("Command String = " + command_str )
		self.queueSerialCmd(command_str)

		dev.updateStateOnServer("setPoint", value = newSetPoint)

		return()

	def setFanSwingMode(self, dev, newFanSwingMode ):
		localProps = dev.pluginProps
		if "ACDevices" in localProps:
			address =  localProps["ACDevices"]
			self.plugin.debugLog("#####  IN handle CHANGE FAN SWING MODE ACTION ###  address of unit is " + address )

		else:
			self.plugin.debugLog("#####  AC Devise not in Plugin Props " + str(localProps) )
			return()

		if newFanSwingMode == "Auto":
			command_str = "swing "+ address + " a" + "\r"
			dev.updateStateOnServer("fanSwing", value="Auto")

		elif newFanSwingMode == "Horiz":
			command_str = "swing "+ address + " h" +  "\r"
			dev.updateStateOnServer("fanSwing", value="Horiz")

		elif newFanSwingMode == "30":
			command_str = "swing "+ address + " 3" +  "\r"
			dev.updateStateOnServer("fanSwing", value="Angle_30")

		elif newFanSwingMode == "45":
			command_str = "swing "+ address + " 4" +  "\r"
			dev.updateStateOnServer("fanSwing", value="Angle_45")

		elif newFanSwingMode == "60":
			command_str = "swing "+ address + " 6" +  "\r"
			dev.updateStateOnServer("fanSwing", value="Angle_60")

		elif newFanSwingMode == "Vert":
			command_str = "swing "+ address + " v" +  "\r"
			dev.updateStateOnServer("fanSwing", value="Vert")

		else:
			self.plugin.debugLog("#####  command line not recognised " + str(newFanSwingMode) + "address" + address )

		return()


	def refreshStatesFromHardware(self, dev, True, False):
		self.queueSerialCmd("stat3")
		return()


