#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# CoolMaster HVAC controller Plugin
# Developed by Ian Burns based (with MUCH gratitude on Jandy Aqualink by J. Yergey
# Dec 2013
################################################################################
# Python imports
import string
import inspect
import time


#local imports from CoolMaster.py
from CoolMaster import CoolMaster
#from hvac_params import hvac_params

##################################################################################################
class Plugin(indigo.PluginBase):

	##############################################################################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		# Initalise Base Class
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		# Debugging Turue generates lots of output
		### TODO ### build Toggle Button for debug output
#		self.debug = True
		self.debug = False
		#####
		# initialse the class
		#####
		self.coolmaster = CoolMaster(self)


	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)

	##############################################################################################
	# Using Built-in control methods from indigo
	##############################################################################################
	def startup(self):
		# All the serial work is handles in comms thread
		pass

	########################################
	def shutdown(self):
		# Once again stop comms thread will tidy up
		pass

	def didDeviceCommPropertyChange(self, origDev, newDev):
		if origDev.deviceTypeId == "CoolMaster_Controller":
			if origDev.pluginProps['devicePort_serialConnType'] != newDev.pluginProps['devicePort_serialConnType']:
				return True
			return False
		elif origDev.deviceTypeId == "HVAC_Unit_CM":
			return False
		else:
			self.errorLog("origDev not recognised in didDevicePropertyChange")



	#######
	### Check serial device <-> config is OK
	### Check serial port is valid
	### If HVAC UNIT is OK then set the state variables
	######
	def validateDeviceConfigUi(self, valuesDict, deviceTypeId, devId):
#		self.debugLog(" --->  FIRST in validate configUI valuesDict = "  +  str(valuesDict) + str(deviceTypeId))
		dev=indigo.devices[devId]
		devProps = dev.pluginProps
		if deviceTypeId == "CoolMaster_Controller":
#			self.debugLog(" --->  in validate configUI valuesDict = "  +  str(valuesDict))
			if len(valuesDict["devicePort_serialConnType"]) == 0:
				# no valid serial port -- show an error.
				errorMsgDict = indigo.Dict()
				self.validateSerialPortUi(valuesDict, errorMsgDict, u"devicePortFieldId")
				self.debugLog(" \nERROR MESSAGES AS FOLLOWS:- " + str(errorMsgDict))
				errorMsgDict["devicePort"] = "Select a valid serial port. If none are listed, then make sure you have installed the FTDI VCP driver."
				return (False, valuesDict, errorMsgDict)
			else:
				########
				##
				##	First check the serial port gets a response and can decode it
				##	if get at least one line pass to values dict to make list.
				##  if OK - indicate no units connected - if Error raise error and stop
				##
				#######


				#######
				##
				##
				##
				#####
				serialUrl = self.getSerialPortUrl(devProps, u"devicePort")
				co_address = serialUrl
				valuesDict["address"]=co_address
				return (True, valuesDict)


		else:  #  assume it is HVAC unit - can add more as they come
#			self.debugLog("\n####################\n###  in configui Props \n##########\n"+ str(dev.pluginProps) + "\n##########")
#			self.debugLog("\n####################\n###  valuesDict \n##########\n"+ str(valuesDict) + "\n##########")

			if "CM_Controllers" in valuesDict:
				co_address = valuesDict["CM_Controllers"] + "-" + valuesDict["ACDevices"]
			else:
				co_address = "unknown"

			self.debugLog("######  coaddress = " + co_address)

			valuesDict["address"]=co_address
			return(True,valuesDict)


	def getDeviceStateList(self, dev):
		#self.debugLog("\n\n HERE are dev data  " + str(dev))
		typeId = dev.deviceTypeId
		self.debugLog("\n\n here is self devices " + str(self.devicesTypeDict[typeId]))
		devId = dev.id

		defaultStatesList = self.devicesTypeDict[typeId]["States"]

		###	CoolMaster Controller States are very simple and ONLY commsActive (True/False) commsConnected(True/False)
		if dev.deviceTypeId == "CoolMaster_Controller":

			commConnected = self.coolmaster.testComms(dev)  #  check comms setup OK
			indigo.server.log(" \n\n  ComConnected   " + str(commConnected))

			if commConnected :
#				indigo.server.log("\n dev defined here look for commConnected state   \n  DEV"  + str(dev) )
				if("commConnected" in defaultStatesList) :
					indigo.server.log(" \n\n  ComConnected indef list   " + str(defaultStatesList['commConnected']))
					defaultStatesList["commConnected"] ="true"
			else :
				defaultStatesList["commConnected"] ="false"
				#pass

		elif dev.deviceTypeId == "HVAC_UNIT_CM":
			self.setHVACUnitProps(dev.id)
			return defaultStatesList

		else:  #  not a recognised type ??
			self.errorLog("not a recogniseed Type? in getDevice State List")
			pass

		return defaultStatesList


	#########################################
	def deviceStartComm(self, dev):
		self.debugLog("<<-- entering deviceStartComm, Device: " + dev.name + "; ID=" +  str(dev.id) + ", Type=" + dev.deviceTypeId)
		if dev.deviceTypeId == "CoolMaster_Controller":
			dev.stateListOrDisplayStateIdChanged()
			self.coolmaster.startCommThread(dev)
		self.debugLog(u"exiting deviceStartComm -->>\n") # + str(dev))

	def deviceStopComm(self, dev):
		self.debugLog("<<-- entering deviceStopComm, Device: " + dev.name + "; ID=" +  str(dev.id) + ", Type=" + dev.deviceTypeId)
		if dev.deviceTypeId == "CoolMaster_Controller":
			self.coolmaster.stopCommThread(dev)
		self.debugLog("exiting deviceStopComm -->>")


	##############################################################################################
	# Actions object callbacks routines
	##############################################################################################
	#################################
	#	MENU Actions
	#
	### MENU action to switch plugin's detailed debugging.
	def toggleDebug(self):
		if self.debug == True:
			self.debug = False
		else:
			self.debug = True
		indigo.server.log("Toggled plugin debugging to " + str(self.debug))


	##########
	#
	#	This sets teh HVAC Unit Properties after it has been created. -
	#	could be doen in Get Device States but this is cleaner
	#
	##########

	def setHVACUnitProps(self , valuesDict, typeId, devId  ):
		dev = indigo.devices[devId]
#		self.debugLog("valuesDict in set HVAC UNIT DATA  = "  + str(valuesDict))
#		self.debugLog("Plugin Props at start "  + str(dev.pluginProps))
		localProps = dev.pluginProps
		localProps.update({"HVAC_ID":valuesDict["ACDevices"]})
#		self.debugLog("Plugin Props at end "  + str(localProps))
		dev.replacePluginPropsOnServer(localProps)



	def collectHVACsonthisCM(self , valuesDict, typeId, devId  ):
		dev=indigo.devices[devId]

#		self.debugLog("\n##############\nvaluesDict = >>" + str(valuesDict) + "\n##########\n")
		if "CM_Controllers" in valuesDict.keys():
			CM_Name = valuesDict["CM_Controllers"]
#			self.debugLog("CM_Name = " + str(CM_Name))
		else:
			self.debugLog("No CM_Controllers in vasluesDict" + str(valuesDict))
			return
		#######
		### First write this selection in Dev props for reference when needed
		### then send stat3 and see load the result
		#######

		for devs in indigo.devices.iter("self"):
#			self.debugLog("devs name = " + str(devs.name))
			if devs.name == CM_Name:
				CM_Id = devs.id
#				self.debugLog("CM_Id = " + str(CM_Id))
			else:
				self.debugLog("No match on devs.name and CM_Name = " + str(CM_Name))

		localProps = dev.pluginProps
		localProps.update({"CMControllerName":CM_Name})
		localProps.update({"CMControllerID":CM_Id})
		dev.replacePluginPropsOnServer(localProps)
#		self.debugLog("\n############\n### UPDATED PROPS\n###CM_NAme => " + CM_Name + "CM_Id = >>" + str(CM_Id)+ "\n#############\n")

#		self.debugLog("\n############\n### output HVAC Unit PArams : = " + str(dev) + "\n#############\n")

		return

	def coolMasterUnitListGenerator(self, filter="", valuesDict=None, typeId="", targetId=0):
#		indigo.server.log("in coolMasterList Generator code")
		dev = indigo.devices[targetId]
#		indigo.server.log("DEV+ " + str(dev))
		localPluginProps = dev.pluginProps
		myArray=[]
		for all_devs in indigo.devices.iter("self"):
#			self.debugLog("all_devs ID = " + str(all_devs.deviceTypeId))
#			self.debugLog("CoolMaster Identified" + str(all_devs.name))
			if all_devs.deviceTypeId == "CoolMaster_Controller":
				myArray.append(all_devs.name)
		if len(myArray) < 1:
			self.debugLog("No Coolmasters created yet")

#		indigo.server.log("myArray before return " + str(myArray))
		return myArray

	def makeHVAClist(self, filter, valuesDict, typeId, devId):
		myArray=[]  # returned array with unconfigured HVAC units from CoolMaster serial reads
		HVACsOnCM = []  #  All HVAC's on this CoolMaster
		HVACsConfiguredAlready = [] #  All configured HVAC's
		CMsConfiguredAlready = []


		HVAC_dev = indigo.devices[devId]  # this is the newly made HVAC Unit
		if "CMControllerID" in HVAC_dev.pluginProps.keys():
			CM_dev_Id = HVAC_dev.pluginProps["CMControllerID"]
#			self.debugLog("parent controller ID is " + str(CM_dev_Id))
			CM_dev = indigo.devices[CM_dev_Id]
		else:
			self.errorLog("ID of controller not defined for this HVAC Unit")
			return myArray



#		self.debugLog("configurred devs name = " + str(CM_dev.name))

		for devs in indigo.devices.iter("self") :
			if devs.deviceTypeId == "HVAC_Unit_CM":
#				self.debugLog("\n######### \nHVAC Plugin Props\n##########\n"+ str(devs.pluginProps) )

				if "CM_Controllers" in devs.pluginProps.keys():
#					self.debugLog("\n######### \nHVAC Plugin Props\n##########\n"+ "CM_cotroller" + devs.pluginProps["CM_Controllers"] + "CM_dev.name = " + CM_dev.name)
					if(devs.pluginProps["CM_Controllers"] == CM_dev.name) :
						HVACsConfiguredAlready.append(devs.pluginProps["ACDevices"])

				else:
					self.errorLog("not finding any keys to make HVAC list")



		self.debugLog("configurred HVAC devs name = " + str(HVACsConfiguredAlready))

		for k in CM_dev.pluginProps.keys():
			k_str = str(k)
#			self.debugLog("k's = " + k_str)
			if  k_str[0:4] == "HVAC" and k_str[-2:] == "ID":
#				self.debugLog("HVAC Item for list = " + k_str)
				name_str = CM_dev.pluginProps[k_str]
				HVACsOnCM.append(name_str)
#		self.debugLog("All HVACs on this CM = " + str(HVACsOnCM))

		for HVAC in HVACsOnCM :
			if HVAC not in HVACsConfiguredAlready:
				myArray.append(HVAC)

#		self.debugLog("\n################\n### myArray List  =>> " +str(myArray)+ "\n###########\n")

		return myArray

# 	def incTemperature(self , info):
# 		dev = indigo.devices[info.deviceId]
# 		self.debugLog("\n############\nDEV = \n "+ str(dev))
# 		current_temp = int(dev.states["setPoint"][:3])
# 		self.debugLog("Increaseing temperature from " + str(current_temp) + " to "  +  str(current_temp+1))
# 		self.coolmaster.setTemp(dev, current_temp + 1)
#
# 	def decTemperature(self , info):
# 		dev = indigo.devices[info.deviceId]
# 		self.debugLog("\n############\nDEV = \n "+ str(dev))
# 		current_temp = int(dev.states["setPoint"][:3])
# 		self.debugLog("Decreaseing temperature from " + str(current_temp) + " to "  +  str(current_temp+1))
# 		self.coolmaster.setTemp(dev, current_temp - 1)


# 	########################################
# 	# Thermostat Action callback
# 	######################
# 	# Main thermostat action bottleneck called by Indigo Server.
# 	def actionControlThermostat(self, action, dev):
# 		###### SET HVAC MODE ######
# 		if action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
# 			self.coolmaster.handleChangeHvacModeAction(dev, action.actionMode)
#
# 		###### SET FAN MODE ######
# 		elif action.thermostatAction == indigo.kThermostatAction.SetFanMode:
# 			self.coolmaster.handleChangeFanModeAction(dev, action.actionMode)
#
# 		###### SET COOL SETPOINT ######
# 		elif action.thermostatAction == indigo.kThermostatAction.SetCoolSetpoint:
# 			newSetpoint = action.actionValue
# 			self.coolmaster.handleChangeSetpointAction(dev, newSetpoint, u"change cool setpoint", u"setpointCool")
#
# 		###### SET HEAT SETPOINT ######
# 		elif action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
# 			newSetpoint = action.actionValue
# 			self.coolmaster.handleChangeSetpointAction(dev, newSetpoint, u"change heat setpoint", u"setpointHeat")
#
# 		###### DECREASE/INCREASE COOL SETPOINT ######
# 		elif action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint:
# 			newSetpoint = dev.coolSetpoint - action.actionValue
# 			self.coolmaster.handleChangeSetpointAction(dev, newSetpoint, u"decrease cool setpoint", u"setpointCool")
#
# 		elif action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint:
# 			newSetpoint = dev.coolSetpoint + action.actionValue
# 			self.coolmaster.handleChangeSetpointAction(dev, newSetpoint, u"increase cool setpoint", u"setpointCool")
#
# 		###### DECREASE/INCREASE HEAT SETPOINT ######
# 		elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
# 			newSetpoint = dev.heatSetpoint - action.actionValue
# 			self.coolmaster.handleChangeSetpointAction(dev, newSetpoint, u"decrease heat setpoint", u"setpointHeat")
#
# 		elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
# 			newSetpoint = dev.heatSetpoint + action.actionValue
# 			self.coolmaster.handleChangeSetpointAction(dev, newSetpoint, u"increase heat setpoint", u"setpointHeat")
#
# 		###### REQUEST STATE UPDATES ######
# 		elif action.thermostatAction in [indigo.kThermostatAction.RequestStatusAll, indigo.kThermostatAction.RequestMode,
# 		indigo.kThermostatAction.RequestEquipmentState, indigo.kThermostatAction.RequestTemperatures, indigo.kThermostatAction.RequestHumidities,
# 		indigo.kThermostatAction.RequestDeadbands, indigo.kThermostatAction.RequestSetpoints]:
# 			self.coolmaster.refreshStatesFromHardware(dev, True, False)

	###################
	#  Specific Action Calls
	####################
	def coolMastergetDataUpdate(self, action, dev_in):
		#  send stat3 and update props/states
		pass



	def coolMasterIncrementThermostat(self, action, dev):
		self.debugLog("###\n  ACTION = " + str(action))
#		dev = indigo.devices[info.deviceId]
		self.debugLog("\n############\nDEV = \n "+ str(dev))
		current_temp = dev.states["setPoint"]
		self.debugLog("Increaseing temperature from " + str(current_temp) + " to "  +  str(current_temp+1))
		self.coolmaster.setTemp(dev, current_temp + 1)


	def coolMasterDecrementThermostat(self, action, dev):
		self.debugLog("###\n  ACTION = " + str(action))
#		dev = indigo.devices[info.deviceId]
		self.debugLog("\n############\nDEV = \n "+ str(dev))
		current_temp = dev.states["setPoint"]
		self.debugLog("Decreaseing temperature from " + str(current_temp) + " to "  +  str(current_temp+1))
		self.coolmaster.setTemp(dev, current_temp - 1)


	def coolMasterSetThermostat(self, action, dev):
		self.debugLog("###\n  ACTION = " + str(action))
		#temporary
		temp = 75
		self.coolmaster.setTemp(dev, temp)
		pass

	def coolMasterSetFanAuto(self, action, dev):
		self.coolmaster.setFanMode( dev, "Auto" )

	def coolMasterSetFanTop(self, action, dev):
		self.coolmaster.setFanMode( dev, "Top" )

	def coolMasterSetFanHi(self, action, dev):
		self.coolmaster.setFanMode( dev, "High" )

	def coolMasterSetFanMed(self, action, dev):
		self.coolmaster.setFanMode( dev, "Med" )

	def coolMasterSetFanLow(self, action, dev):
		self.coolmaster.setFanMode(dev, "Low" )

	def coolMasterSetAllOff(self, action, dev):
		self.coolmaster.setMode( dev, "Alloff" )

	def coolMasterSetAllOn(self, action, dev):
		self.coolmaster.setMode( dev, "Allon" )

	def coolMasterSetOff(self, action, dev):
		self.coolmaster.setMode( dev, "Off" )

	def coolMasterSetOn(self, action, dev):
		self.coolmaster.setMode( dev, "On" )

	def coolMasterTogglePower(self, action, dev):
	    if ((dev.states["power"]) == "On" or (dev.states["power"] == "ON") or (dev.states["power"] == "on")) :
	        self.coolmaster.setMode( dev, "Off" )
	    else:
	        self.coolmaster.setMode( dev, "On" )

	def coolMasterSetCool(self, action, dev):
		self.debugLog("\n############\nIN SET COOL = \n ")
		self.coolmaster.setMode( dev, "Cool" )

	def coolMasterSetHeat(self, action, dev):
		self.coolmaster.setMode( dev, "Heat" )

	def coolMasterSetDry(self, action, dev):
		self.coolmaster.setMode( dev, "Dry" )

	def coolMasterSetFan(self, action, dev):
		self.coolmaster.setMode( dev, "Fan" )

	def coolMasterSetSwingAuto(self, action, dev):
		self.coolmaster.setFanSwingMode( dev,"Auto")

	def coolMasterSetSwingHoriz(self, action, dev):
		self.coolmaster.setFanSwingMode( dev,"Horiz")

	def coolMasterSetSwing30(self, action, dev):
		self.coolmaster.setFanSwingMode( dev,"30")

	def coolMasterSetSwing45(self, action, dev):
		self.coolmaster.setFanSwingMode( dev,"45")

	def coolMasterSetSwing60(self, action, dev):
		self.coolmaster.setFanSwingMode( dev,"60")

	def coolMasterSetSwingVert(self, action, dev):
		self.coolmaster.setFanSwingMode( dev,"Vert")




