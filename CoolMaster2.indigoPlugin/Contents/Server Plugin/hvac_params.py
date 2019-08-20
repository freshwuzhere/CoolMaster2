import os
import sys
import string
import indigo

class hvac_params():	
	def convert_temp(self, val , tempInCorF):
		# CooolMaster appears to only support Celsius now so depending on setting we ned to convert (or not :)
		# could build test for input string form coolmaser that includes C or F appendtion
		
		if tempInCorF  == "C2F":
			convTemp = val * 9.0/5.0 + 32.0
		elif tempInCorF == "F2C":
			convTemp = (val - 32.0) * 5.0/9.0
		elif tempInCorF == "C2F_rel":
			convTemp = val * 9.0/5.0
		elif tempInCorF == "F2C_rel":	
			convTemp = val * 5.0/9.0
		else: 
			convTemp = val
		return(convTemp)
		
	def test_fan_string(self,fan_mode):
		if fan_mode=="Low" or fan_mode=="Med" or fan_mode=="High" or fan_mode=="Auto" or fan_mode=="Top" :
			return(True)
		else:
			return(False)

	def test_mode_string(self,mode):
		if mode=="Auto" or mode=="Cool" or mode=="Heat" or mode=="Fan" or mode == "Dry":
			return(True)
		else:
			return(False)

	def test_error_codes(self, code):
		if code != "OK":
			if code[1] == "X":
				return(False)
		else:
			return(True)
		return(True)	
	
address = u"XXX"
on_off_state = True
set_temp = 0.0
room_temp = 0.0
fan_speed = u""
mode = u""
code = u""
filter = 0
