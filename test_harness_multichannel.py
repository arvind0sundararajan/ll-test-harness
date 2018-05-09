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
import matplotlib.pyplot as plt
import numpy as np

class Experiment:
	"""Called by main. Holds all experiment bookkeeping and logging information.
	Opens connection with AD2, runs main test harness loop, closes.
	"""

	def __init__(self, button_press_channel, button_press_mirror_channel, packet_created_channel, packet_received_channel,packet_received_channel_2,killswitch_channel):
		self.ad2 = AnalogDiscoveryUtils()
		self.button_press_bit_mask = (1<<button_press_channel)
		self.button_press_mirror_bit_mask = (1<<button_press_mirror_channel)
		self.packet_created_bit_mask = (1<<packet_created_channel)
		self.packet_received_bit_mask = (1<<packet_received_channel) | (1<<packet_received_channel_2)
        	self.packet_received_channel_1 = (1<<packet_received_channel) 
        	self.packet_received_channel_2 =(1<<packet_received_channel_2) 
		self.packet_latencies = []
		self.killswitch_mask = (1<<killswitch_channel)
		self.channel_1 = packet_received_channel
		self.channel_2 = packet_received_channel_2
		self.sampling_freq = -1

	def write_data_to_file(self, file_to_write):
		with open(file_to_write, "a") as f:
			f.write("Packet, Latency 1 (ms), Latency 2 (ms), Minimum Latency\n")

			i = 1
			for latencies in self.packet_latencies:
				f.write("{}, {}, {}, {}\n".format(i, latencies[0],latencies[1],latencies[2]))
				i += 1

		return

	def write_anomoly_data_to_file(self, file_to_write, data,data_dir,debounce):
		
		if debounce:
			dir_name = data_dir[0:-4]+"debounce"
		else:
			dir_name = data_dir[0:-4]+"anomalies"			
 
		if not os.path.exists(dir_name):
   			os.makedirs(dir_name)
		with open(dir_name+"/"+file_to_write+".csv", "a") as f:
			f.write("Time, Mote 1 Rx Signal, Mote 2 Rx Signal\n")

			i = 1
			for point in data:
				chan1index = 15 - self.channel_1
				chan2index = 15-self.channel_2 
				bitstring = "{:016b}".format(point)
				f.write("{:7f}, {},{}\n".format(float(i)/self.sampling_freq,bitstring[chan1index],bitstring[chan2index]))

				i += 1

		return

	def postprocess(self, array_of_samples, steady_state_DIO,sample_rate,packet_num,data_dir_name):
		"""Postprocesses the array of samples to return the latency of this packet.
		Corresponds to the first sample offset which shows a difference in the packet received channel.
		"""
		#print 'Postprocessing.'
		packet_received_initial_state = steady_state_DIO & self.packet_received_bit_mask
		
		# sample offset
		i = 0
		# latency in ms
		latency1 = 0
        	latency2 = 0
		min_latency = 0

		packet_received = False
		#ack_missed = True
		packet_1_received = False
		packet_2_received = False


		triggered1 = False
		toggle1_verified = False
		timesteps_triggered1 = 0
		debounce_timesteps = 5 #length of period that we gather data until the debounce
		debounce_requirement = 3  # number of timesteps required for a toggle to stay constant in order for it to be counted as a toggle
		sample_buf = []
		sample_buf = []
		trigger_sample = 0
		debounce_reject = False
		for sample in array_of_samples:
			i += 1


			
			if (sample & self.packet_received_channel_1) != (packet_received_initial_state & self.packet_received_channel_1):
				#block is first entered for first sample offset where pin changed state
				if packet_1_received == False:
					#latency = (i / 100.0)
					latency1 = (i / float(sample_rate))
					packet_1_received = True
					
					if packet_received == False:
						packet_received = True
						min_latency = latency1

					


			if (sample & self.packet_received_channel_2) != (packet_received_initial_state & self.packet_received_channel_2):
				#block is first entered for first sample offset where pin changed state
				if packet_2_received == False:
					#latency = (i / 100.0)
					latency2 = (i / float(sample_rate))
					packet_2_received = True
					
					if packet_received == False:
						packet_received = True
						min_latency = latency2

			
			if(packet_1_received and packet_2_received):
				break			

			"""
			if ((sample & self.packet_created_channel) == (steady_state_DIO & self.packet_created_channel)) and packet_received:
				ack_missed = False
				break
			"""
			



		if ( (latency1 < 0.7 and latency1>0) or (latency2 < 0.7 and latency2>0) or (latency1 < 1.4 and latency1>0.9) or (latency2 < 1.4 and latency2>0.9)):
			self.write_anomoly_data_to_file(str(packet_num),array_of_samples,data_dir_name,False)
		if debounce_reject:
			self.write_anomoly_data_to_file(str(packet_num),array_of_samples,data_dir_name,True)
			debounce_reject = False
		self.packet_latencies.append((latency1,latency2,min_latency))
			
		return latency1, latency2, min_latency


	def run(self, num_packets,sample_length):
		#main loop of experiment
		experiment_start_time = time.strftime("%H_%M_%S_%m_%d_%Y", time.localtime())
		print "starting dataset at {}\n".format(experiment_start_time)
		data_file = experiment_start_time + ".csv"

		exp_start = time.time()
		# open connection to device
		self.ad2.open_device()


        	sample_rate = 4096/float(sample_length) #in khz
        	sample_divider = int(100000/sample_rate)
        	sample_rate = 100000/float(sample_divider) #returns the actual sample rate
		self.sampling_freq=sample_rate
        	print "Sample Rate: {}\n".format(sample_rate)
        	print "Sample Divider: {}\n".format(sample_divider)

		for i in range(num_packets):

			sts = c_byte()
			rgwSamples = (c_uint16*self.ad2.cSamples)()

			packet_received = False
			#configure tx button and killswitch as outputs
			self.ad2.configure_digitalIO(self.button_press_bit_mask|self.killswitch_mask)
			self.ad2.configure_digitalIn(self.button_press_mirror_bit_mask,sample_divider)


			#print "steady_state_DIO: {}".format(binary_num_str(steady_state_DIO))

			#delay button press so digitalIn is armed
			# button uniformly distributed over 110ms slotframe
			#wait = random.randint(0, 2) + 2
			wait = 10
			time.sleep(wait * 0.001)
			#turn off killswitch to allow resends to happen
			self.ad2.button_depress()

			#get initial state of DIO pins
			steady_state_DIO = self.ad2.get_DIO_values()
			#press button
			self.ad2.button_press(self.button_press_bit_mask)
            		#print "button pressed"


			while True:
				self.ad2.dwf.FDwfDigitalInStatus(self.ad2.interface_handler, c_int(1), byref(sts))
				#if sts.value !=1:
					#print "STS VAL: " + str(sts.value)
				#print stsDone.value
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
			self.ad2.button_press(self.killswitch_mask)
			curr_latency = self.postprocess(rgwSamples, steady_state_DIO,sample_rate,i,data_file)
			print "{}: {:.5f}   {:.5f}   {:.5f}".format(i+1, curr_latency[0],curr_latency[1],curr_latency[2])


		self.ad2.close_device()

		self.write_data_to_file(data_file)

		exp_stop = time.time()

		print "Done with experiment."
		print "Total duration: {}".format(exp_stop - exp_start)
		print "Sample Rate: {}".format(sample_rate)
		print "Sample Divider: {}".format(sample_divider)
		np_latencies = np.asmatrix(self.packet_latencies)
		plt.figure()
		plt.hist(np_latencies[:,0],1000,log=True)

		plt.figure()
		plt.hist(np_latencies[:,1],1000,log=True)

		plt.figure()
		plt.hist(np_latencies[:,2],1000,log=True)
		print np_latencies[:,2]
		#print np_latencies
		plt.show()
		return



class AnalogDiscoveryUtils:
	"""Collection of variables, functions to interact with AD2.
	"""

	def __init__(self):
		self.dwf = None
		self.interface_handler = None

		# set number of sample to acquire (DEPENDING ON NUMBER OF ACTIVE SLOTS)
		self.cSamples = 4096

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


	def configure_digitalIn(self, button_press_mirror_channel,sample_divider):
		self.dwf.FDwfDigitalInReset(self.interface_handler)

		#sample rate = system frequency / divider, 100MHz/ 1000 = 100 kHz
		#self.dwf.FDwfDigitalInDividerSet(self.interface_handler, c_int(1000))
		self.dwf.FDwfDigitalInDividerSet(self.interface_handler, c_int(sample_divider))		# 16bit per sample format
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
	# button_press_channel, button_press_mirror_channel(wired to button press channel), packet_created_channel, packet_received_channel, packetrx2 channel,killswitch
	my_experiment = Experiment(0, 8, 7, 15, 14,1)
    	sample_length = 10 #length of time you want to sample for in ms
	try:
		my_experiment.run(1000000,sample_length)

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
