from ctypes import *
from dwfconstants import *
import sys
import time

dwf = None

class AnalogDiscoveryUtils:

	def __init__(self, sampling_freq_user_input):
		self.interface_handler = None

		self.internal_clock_freq = 0
		self.sampling_freq = sampling_freq_user_input
		self.period_ms = (1000.0 / self.sampling_freq)


		# bit representations of the AD2 DIO channels
		# index is 1 if that pin is included in input/output
		# TODO: change this
		self.input_channels_bit_rep = 0x8100
		self.output_channels_bit_rep = 0x81


	def open_device(self):
		"""Opens the connection to AD2.
		   Sets the class attribute post-connection dwf interface_handler
			   object, as well as the internal clock frequency.
		"""
		# open device
		# declare ctype variables
		hdwf = c_int()

		print "\nOpening device"
		dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

		if self.interface_handler.value == 0:
			print "failed to open device"
			quit()

		self.interface_handler = hdwf

		hzSysIn = c_double()
		#max_buffer_size_in = c_int()

		dwf.FDwfDigitalInInternalClockInfo(self.interface_handler, byref(hzSysIn))
		#dwf.FDwfDigitalInBufferSizeInfo(self.interface_handler, byref(max_buffer_size_in))

		self.internal_clock_freq = hzSysIn.value

		#print "internal digital in frequency is " + str(hzSysIn.value)
		#print "digital in max buffer size: " + str(max_buffer_size_in.value)


	def close_device(self):
		"""Resets instruments and closes the connection to AD2."""
		
		# reset DigitalIO instrument
		dwf.FDwfDigitalIOReset()

		#reset DigitalIn instrument
		dwf.FDwfDigitalInReset(ad_utils.interface_handler)

		dwf.FDwfDeviceCloseAll()
		print "device closed\n"


	def _configure_DigitalOut(self):
		"""Configure digital out.
		Output a 10 Hz clock on DIO 0, 
		5 Hz clock on DIO 7.
		"""
		dwf.FDwfDigitalOutReset(self.interface_handler);

		# 10 Hz pulse on DIO 0
		dwf.FDwfDigitalOutEnableSet(self.interface_handler, c_int(0), c_int(1))
		# prescaler to 10 Hz,
		dwf.FDwfDigitalOutDividerSet(self.interface_handler, c_int(0), c_int(10000000))
		# 1 tick low, 1 tick high
		dwf.FDwfDigitalOutCounterSet(self.interface_handler, c_int(0), c_int(1), c_int(1))

		# 5 Hz pulse on DIO 7
		dwf.FDwfDigitalOutEnableSet(self.interface_handler, c_int(7), c_int(1))
		# prescaler to 10 Hz, 
		dwf.FDwfDigitalOutDividerSet(self.interface_handler, c_int(0), c_int(20000000))
		# 1 tick low, 1 tick high
		dwf.FDwfDigitalOutCounterSet(self.interface_handler, c_int(0), c_int(1), c_int(1))

		dwf.FDwfDigitalOutConfigure(self.interface_handler, c_int(1))



	def _configure_DigitalIn(self, num_samples):
		"""configure DigitalIn instrument for the experiment.
		Configures the trigger when the channel represented by trigger_channel_bit_rep is high.
		Configures instrument to take num_samples to take after trigger. 

		NOTE: both arguments are ints, not c_int()
		"""

		#reset DigitalIn instrument
		dwf.FDwfDigitalInReset(self.interface_handler)

		# in record mode samples after trigger are acquired only
		dwf.FDwfDigitalInAcquisitionModeSet(self.interface_handler, acqmodeRecord)
		# set clock divider so 100 MHz / self.sampling_freq = divider
		dwf.FDwfDigitalInDividerSet(self.interface_handler, c_int((int) (100000000 / self.sampling_freq)))
		# take 16 bits per sample
		dwf.FDwfDigitalInSampleFormatSet(self.interface_handler, c_int(16))

		# take num_samples after trigger
		dwf.FDwfDigitalInTriggerPositionSet(self.interface_handler, c_int(num_samples))
		# set trigger source to AD2 DigitalIn channels
		dwf.FDwfDigitalInTriggerSourceSet(self.interface_handler, trigsrcDetectorDigitalIn)
		# set DigitalIn trigger on DIO 7 rising edge
		dwf.FDwfDigitalInTriggerSet(self.interface_handler, c_int(0), c_int(0), c_int(0x80), c_int(0))

		# start acquisition; should wait for trigger
		dwf.FDwfDigitalInConfigure(self.interface_handler, c_bool(0), c_bool(1))

		#print "Configured DigitalIn."



	def _get_DigitalIn_status(self, read_data=False):
		"""Returns the c_ubyte() object corresponding to the instrument state.
		"""
		status = c_byte()
		if read_data:
			dwf.FDwfDigitalInStatus(self.interface_handler, c_int(1), byref(status))

		dwf.FDwfDigitalInStatus(self.interface_handler, c_int(0), byref(status))
		return status
	

	def _copy_buffer_samples(self, buffer_info, nSamples, arr, copy_all_samples=False, last_read=False):
		"""Copies samples from the AD2 buffer to arr (located on computer memory).
		Returns the updated cSamples.
		"""
		cAvailable = c_int()
		cLost = c_int()
		cCorrupted = c_int()
		cSamples = buffer_info[0]

		# get DigitalIn status because we want to read from buffer
		self._get_DigitalIn_status(read_data=True)

		# record info about the data collection process (filling of the buffer)
		dwf.FDwfDigitalInStatusRecord(self.interface_handler, byref(cAvailable), byref(cLost), byref(cCorrupted))

		if copy_all_samples:
			dwf.FDwfDigitalInStatusData(self.interface_handler, byref(arr), c_int(2*4096))
			return [0, 0, 0]

		cSamples += cLost.value
		if cSamples + cAvailable.value > nSamples:
			cAvailable = c_int(nSamples - cSamples)

		# copy samples to arr on computer
		dwf.FDwfDigitalInStatusData(self.interface_handler, byref(arr, 2*cSamples), c_int(2*cAvailable.value))

		cSamples += cAvailable.value

		buffer_info = [cSamples, buffer_info[1] + cLost.value, buffer_info[2] + cCorrupted.value]
		return buffer_info

	def test(self):
		experiment_start_time = time.strftime("%H_%M_%S_%m_%d_%Y", time.localtime())
		data_file = "test_" + experiment_start_time + ".csv"

		with open(data_file, 'a') as f:
			f.write("Offset, Sample\n")

		nSamples = (int) (1.5 * self.sampling_freq)

		#csamples, lost, corrupted
		buffer_info = [0, 0, 0]

		while buffer_info[0] <= nSamples:
			


if __name__ == "__main__":

	if sys.platform.startswith("win"):
		dwf = cdll.dwf
	elif sys.platform.startswith("darwin"):
		dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
	else:
		dwf = cdll.LoadLibrary("libdwf.so")

	# print DWF version
	version = create_string_buffer(16)
	dwf.FDwfGetVersion(version)
	print "DWF Version: " + version.value

	ad_utils = AnalogDiscoveryUtils(1000000)
	ad_utils.open_device()

	try:
		ad_utils.test()
	except KeyboardInterrupt:
		dwf.FDwfDigitalOutReset(ad_utils.interface_handler)
		ad_utils.close_device()

	ad_utils.close_device()
	sys.exit(0)