"""
   Updated test harness for the low latency experiment.

   Written by Alex Yang, Arvind Sundararajan, Craig Schindler
   2/9/2017

   Requires:                       
       Python 2.7
       python-dateutil
"""
from ctypes import *
from dwfconstants import *
import time
import sys


class Experiment:
	"""Called by main. Holds all experiment bookkeeping and logging information.
	Opens connection with AD2, runs main test harness loop, closes.
	"""

	def __init__(self):
		pass



def binary_num_str(num, split=True):
  """returns a string of num in binary form in chunks of 4.
  Makes it easier to read.
  """
  num_bin_str = "{}".format(bin(num))[2:].zfill(16)
  if not split:
    return num_bin_str

  num_chunks = [num_bin_str[4*i:4*(i+1)] for i in xrange(len(num_bin_str)//4)]
  output_str = ""
  for chunk in num_chunks:
    output_str += "{} ".format(chunk)
  return output_str


def get_DIO_values(hdwf):
	dio_pins = c_uint16()

	# fetch digital IO information from the device 
	dwf.FDwfDigitalIOStatus(hdwf) 
	# read state of all pins, regardless of output enable
	dwf.FDwfDigitalIOInputStatus(hdwf, byref(dio_pins)) 

	return dio_pins.value



if __name__ == '__main__':

	if sys.platform.startswith("win"):
		dwf = cdll.dwf
	elif sys.platform.startswith("darwin"):
		dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
	else:
		dwf = cdll.LoadLibrary("libdwf.so")

	#declare ctype variables
	hdwf = c_int()
	sts = c_byte()

	#print DWF version
	version = create_string_buffer(16)
	dwf.FDwfGetVersion(version)
	print "DWF Version: "+version.value

	#open device
	print "Opening first device"
	dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

	if hdwf.value == hdwfNone.value:
		print "failed to open device"
		quit()

	print "Preparing to read sample..."


	# enable output/mask on 8 LSB IO pins, from DIO 0 to 7
	#dwf.FDwfDigitalIOOutputEnableSet(hdwf, c_int(0x00FF)) 
	# set value on enabled IO pins
	#dwf.FDwfDigitalIOOutputSet(hdwf, c_int(0x12)) 

	#set so we can exit early before buffer is filled
	#dwf.FDwfDigitalInAcquisitionModeSet(hdwf, acqmodeRecord)

	#sample rate = system frequency / divider, 100MHz/1
	dwf.FDwfDigitalInDividerSet(hdwf, c_int(50000))
	# 16bit per sample format
	dwf.FDwfDigitalInSampleFormatSet(hdwf, c_int(16))
	# set number of sample to acquire (DEPENDING ON NUMBER OF ACTIVE SLOTS)
	cSamples = 4096
	rgwSamples = (c_uint16*cSamples)()
	dwf.FDwfDigitalInBufferSizeSet(hdwf, c_int(cSamples))


	dwf.FDwfDigitalInTriggerSourceSet(hdwf, c_ubyte(3)) # trigsrcDetectorDigitalIn
	dwf.FDwfDigitalInTriggerPositionSet(hdwf, c_int(cSamples))
	dwf.FDwfDigitalInTriggerSet(hdwf, c_int(0), c_int(0), c_int(1), c_int(0)) # DIO0 rising

	# begin acquisition
	dwf.FDwfDigitalInConfigure(hdwf, c_bool(0), c_bool(1))
	print "   waiting to finish"

	start_DIO_values = get_DIO_values(hdwf)
	print "start_DIO_values: {}".format(binary_num_str(start_DIO_values))
	packet_received_bit_mask = 0x8000

	packet_received = False

	while True:
		dwf.FDwfDigitalInStatus(hdwf, c_int(1), byref(sts))
		#print "STS VAL: " + str(sts.value)
		if sts.value == stsDone.value:
			print "Done"
			break

		curr_DIO_values = get_DIO_values(hdwf)
		if (((curr_DIO_values ^ start_DIO_values) & packet_received_bit_mask) != 0) and not packet_received:
			print "curr_DIO_values: {}".format(binary_num_str(curr_DIO_values))
			# packet received      	
			print "Pkt received"
			packet_received = True
			
	# get samples, byte size
	dwf.FDwfDigitalInStatusData(hdwf, byref(rgwSamples), 2*cSamples)
	
	#close device 
	dwf.FDwfDeviceCloseAll()


	with open("test_sampling.csv", "a") as data_file:
		data_file.write("Sample offset, Sample\n")

		i = 0
		for sample in rgwSamples:
		    data_file.write("{}, {}\n".format(i, binary_num_str(rgwSamples[i], split=True)))
		    i += 1


