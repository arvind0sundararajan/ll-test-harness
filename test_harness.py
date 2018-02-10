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
import logging
import os
import random
import sys
import time


class Experiment:
	"""Called by main. Holds all experiment bookkeeping and logging information.
	Opens connection with AD2, runs main test harness loop, closes.
	"""

	def __init__(self, button_press_channel, button_press_mirror_channel, packet_created_channel, packet_received_channel):
		self.ad2 = AnalogDiscoveryUtils()
		self.button_press_bit_mask = (1<<button_press_channel)
		self.button_press_mirror_bit_mask = (1<<button_press_mirror_channel)
		self.packet_created_bit_mask = (1<<packet_created_channel)
		self.packet_received_bit_mask = (1<<packet_received_channel)

		self.packet_latencies = []



	def write_data_to_file(self, file_to_write):
		with open(file_to_write, "a") as f:
			f.write("Packet, Latency (ms)\n")

			i = 1
			for latency in self.packet_latencies:
				f.write("{}, {}\n".format(i, latency))
				i += 1

		return


	def postprocess(self, array_of_samples, steady_state_DIO):
		"""Postprocesses the array of samples to return the latency of this packet.
		Corresponds to the first sample offset which shows a difference in the packet received channel.
		"""
		#print 'Postprocessing.'
		packet_received_initial_state = steady_state_DIO & self.packet_received_bit_mask
		
		# sample offset
		i = 0
		# latency in ms
		latency = 0

		packet_received = False
		#ack_missed = True


		for sample in array_of_samples:
			i += 1
			if (sample & self.packet_received_bit_mask) != packet_received_initial_state:
				#block is first entered for first sample offset where pin changed state
				latency = (i / 2.0)
				packet_received = True
				break

			"""
			if ((sample & self.packet_created_channel) == (steady_state_DIO & self.packet_created_channel)) and packet_received:
				ack_missed = False
				break
			"""

		self.packet_latencies.append(latency)
		return latency


	def run(self, num_packets):
		#main loop of experiment
		experiment_start_time = time.strftime("%H_%M_%S_%m_%d_%Y", time.localtime())
		print "starting dataset at {}\n".format(experiment_start_time)
		data_file = experiment_start_time + ".csv"

		exp_start = time.time()
		# open connection to device
		self.ad2.open_device()


		for i in range(num_packets):

			sts = c_byte()
			rgwSamples = (c_uint16*self.ad2.cSamples)()

			packet_received = False

			self.ad2.configure_digitalIO(self.button_press_bit_mask)
			self.ad2.configure_digitalIn(self.button_press_mirror_bit_mask)

			#get initial state of DIO pins
			steady_state_DIO = self.ad2.get_DIO_values()
			#print "steady_state_DIO: {}".format(binary_num_str(steady_state_DIO))

			#delay button press so digitalIn is armed
			# button uniformly distributed over 110ms slotframe
			wait = random.randint(0, 110) + 5
			time.sleep(wait * 0.001)


			#press button
			self.ad2.button_press(self.button_press_bit_mask)

			while True:
				self.ad2.dwf.FDwfDigitalInStatus(self.ad2.interface_handler, c_int(1), byref(sts))
				#print "STS VAL: " + str(sts.value)
				if sts.value == stsDone.value:
					#print "Done sampling."
					break

				curr_DIO_values = self.ad2.get_DIO_values()
				#print "curr_DIO_values: {}".format(binary_num_str(curr_DIO_values))
				if (((curr_DIO_values ^ steady_state_DIO) & self.packet_received_bit_mask) != 0) and not packet_received:
					#print "curr_DIO_values: {}".format(binary_num_str(curr_DIO_values))
					# packet received      	
					#print "Pkt received"
					packet_received = True
					self.ad2.button_depress()

					
			self.ad2.read_buffer(rgwSamples)
			curr_latency = self.postprocess(rgwSamples, steady_state_DIO)
			print "{}: {}".format(i+1, curr_latency)


		self.ad2.close_device()

		self.write_data_to_file(data_file)

		exp_stop = time.time()
		print "Done with experiment."
		print "Total duration: {}".format(exp_stop - exp_start)
		return



class AnalogDiscoveryUtils:
	"""Collection of variables, functions to interact with AD2.
	"""

	def __init__(self):
		self.dwf = None
		self.interface_handler = None

		# set number of sample to acquire (DEPENDING ON NUMBER OF ACTIVE SLOTS)
		self.cSamples = 400

		self._setup_dwf_library()


	def _setup_dwf_library(self):

		if sys.platform.startswith("win"):
			self.dwf = cdll.dwf
		elif sys.platform.startswith("darwin"):
			self.dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
		else:
			self.dwf = cdll.LoadLibrary("libdwf.so")

		#print DWF version
		version = create_string_buffer(16)
		self.dwf.FDwfGetVersion(version)
		print "DWF Version: "+ version.value
		return

	def open_device(self):
		"""Opens the connection to AD2.
		   Sets the class attribute post-connection dwf interface_handler
			   object, as well as the internal clock frequency.
		"""
		# open device
		# declare ctype variables
		hdwf = c_int()

		print "Opening device"
		self.dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

		if hdwf.value == 0:
			print "failed to open device"
			quit()

		self.interface_handler = hdwf

	def close_device(self):
		#close device 
		self.dwf.FDwfDeviceCloseAll()
		print "Device closed"


	def configure_digitalIn(self, button_press_mirror_channel):
		self.dwf.FDwfDigitalInReset(self.interface_handler)

		#sample rate = system frequency / divider, 100MHz/ 50000 = 2 kHz
		self.dwf.FDwfDigitalInDividerSet(self.interface_handler, c_int(50000))
		# 16bit per sample format
		self.dwf.FDwfDigitalInSampleFormatSet(self.interface_handler, c_int(16))

		self.dwf.FDwfDigitalInBufferSizeSet(self.interface_handler, c_int(self.cSamples))


		#print "Setting trigger: {}".format(binary_num_str(button_press_mirror_channel))


		self.dwf.FDwfDigitalInTriggerPositionSet(self.interface_handler, c_int(self.cSamples))
		self.dwf.FDwfDigitalInTriggerSourceSet(self.interface_handler, c_ubyte(3)) # trigsrcDetectorDigitalIn
		self.dwf.FDwfDigitalInTriggerSet(self.interface_handler, c_int(0), c_int(0), c_int(button_press_mirror_channel), c_int(0)) # DIO8 rising

		# begin acquisition
		self.dwf.FDwfDigitalInConfigure(self.interface_handler, c_bool(0), c_bool(1))
		#print "Configured DigitalIn."
		return


	def get_digitalIn_status(self):
		"""Returns the status of the DigitalIn module.
		"""
		sts = c_byte()
		return 0


	def configure_digitalIO(self, output_bit_mask):
		# reset DigitalIO instrument
		self.dwf.FDwfDigitalIOReset()

		# enable output/mask 
		#print "Enabling output: {}".format(binary_num_str(output_bit_mask))
		self.dwf.FDwfDigitalIOOutputEnableSet(self.interface_handler, c_int(output_bit_mask)) 
		return		


	def button_press(self, button_press_channel):
		#print "button pressed"
		# set value on enabled IO pins
		self.dwf.FDwfDigitalIOOutputSet(self.interface_handler, c_uint16(button_press_channel)) 
		return



	def button_depress(self):
		# reset
		self.dwf.FDwfDigitalIOOutputSet(self.interface_handler, c_uint16(0))
		return


	def read_buffer(self, array_to_write):
		#print "Reading buffer contents."
		sts = c_byte()
		self.dwf.FDwfDigitalInStatus(self.interface_handler, c_int(1), byref(sts))

		# get samples, byte size
		self.dwf.FDwfDigitalInStatusData(self.interface_handler, byref(array_to_write), 2*self.cSamples)

		return array_to_write


	def get_DIO_values(self):
		dio_pins = c_uint16()

		# fetch digital IO information from the device 
		self.dwf.FDwfDigitalIOStatus(self.interface_handler) 
		# read state of all pins, regardless of output enable
		self.dwf.FDwfDigitalIOInputStatus(self.interface_handler, byref(dio_pins)) 

		return dio_pins.value


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






if __name__ == '__main__':

	my_experiment = Experiment(0, 8, 7, 15)

	try:
		my_experiment.run(10000)

	except KeyboardInterrupt:
		my_experiment.ad2.close_device()
		sys.exit(1)


	sys.exit()



	

	"""
	with open("test_sampling.csv", "a") as data_file:
		data_file.write("Sample offset, Sample\n")

		i = 0
		for sample in rgwSamples:
		    data_file.write("{}, {}\n".format(i, binary_num_str(rgwSamples[i], split=True)))
		    i += 1
	"""

