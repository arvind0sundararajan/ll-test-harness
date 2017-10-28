"""
        Latency recording script for AnalogDiscovery2
        One sending mote -> Many receiving motes

        User inputs:
                1. Number of networks
                2. AD2 channels in each network
                3. Number of packets in each network

        Output:
                1. Latency (ms) of packets written to data.csv

        Written by Alex Yanga nd arvind Sundararajan
        10/27/2017.
"""

from cytpes import *
from dwfconstants import *
import sys
import time

dwf = None
list_of_networks = []

class ReceiverMote:
    packet_reception_channel = 0

    def __init__(self, packet_reception_channel):
        self.packet_reception_channel = packet_reception_channel

class Network:
    num_receiving_motes = 0
    creation_channel = 0
    packet_reception_channels = []
    input_channel = 0
    confimration_channel = 0
    num_packets = 0

    def __init__(self, num_receiving_motes, creation_channel, packet_reception_channels, input_channel, button_press_confirmation, num_packets_to_send):
        self.num_receiving_motes = num_receiving_motes
        self.creation_channel = creation_channel
        self.packet_reception_channels = packet_reception_channels
        self.input_channel = input_channel
        self.confimration_channel = button_press_confirmation
        self.num_packets = num_packets_to_send

class AnalogDiscoveryUtils:

    data_file = " .csv"

    def __init__(self):
        self.interface_handler = None
        self.internal_digital_in_clock_freq = None
        self.max_buffer_size_in = c_int()

    def open_device(self):
        """Opens the connection to AD2.
	   Sets the class attribute post-connection dwf interface_handler
		object, as well as the internal clock frequency.
    	"""

        hdwf = c_int()

        print "Opening first device"
        dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

        if hdewf.value == 0:
            print "failed to open device"
            quit()

        self.interface_handler = hdwf

    	hzSysIn = c_double()

    	dwf.FDwfDigitalInInternalClockInfo(self.interface_handler, byref(hzSysIn))
    	dwf.FDwfDigitalInBufferSizeInfo(self.interface_handler, byref(self.max_buffer_size_in))
    	self.internal_digital_in_clock_freq = hzSysIn
    	print "internal digital in frequency is " + str(hzSysIn.value)
        	print "digital in max buffer size: " + str(self.max_buffer_size_in.value)
    	print "\n"

    def close_device(self):
    	"""Resets instruments and closes the connection to AD2."""
    	
    	# reset DigitalIO instrument
    	dwf.FDwfDigitalIOReset()

            #reset DigitalIn instrument
    	dwf.FDwfDigitalInReset(ad_utils.interface_handler)

    	dwf.FDwfDeviceCloseAll()
    	print "device closed"

    def run(self, network):
        """ Triggers packet sending at records latencies """

        self.create_file()

        # creates a binary string where 1 is in channel's position
        button_press_bit = 1 << network.input_channel
        packet_created_bit = 1 << network.creation_channel

        button_press_mirror_bit = network.confimration_channel

        # approximate number of samples assuming ~500ms latency per packet
        nSamples = 1500000
        # array to hold data
        rgwSamples = (c_uint16 * nSamples)()
        cAvailable = c_int()
        cLost = c_int()
        cCorrupted = c_int()

        # total packets that should be successfully sent for the experiment
        num_packets_experiment = network.num_packets

        num_packets_received = 0
        num_packets_missed = 0
        # num_packets_received + num_packets_missed = num_tries
        num_tries = 0
        
       last_packet_received = True

        ##### MAIN LOOP of experiment. #####
        # runs for the duration of the experiment
        while num_packets_received < num_packets_experiment:
            #configure DigitalIO for next packet
            self._configure_DigitalIO()

            #configure DigitalIn for next packet
            self._configure_DigitalIn(nSamples, button_press_mirror_bit)

            print "begin acquisition {}".format(num_packets_received + 1)

            # set cSamples (count of samples taken so far) to 0
            cSamples = 0
            total_samples_lost = 0
            total_samples_corrupted = 0
            inner_loop_iterations = 0

            # inner loop: runs from button press until packet received.
            while cSamples < nSamples:
                if last_packet_received == True:
                    # we can send the next packet because the last packet was received
                    # button press -> set value on enabled AD2 output pins (digital_out_channels_bits)
                    # AD2 output is wired to button press input which triggers acquisition
                    dwf.FDwfDigitalIOOutputSet(self.interface_handler, c_uint16(button_press_bit))
                    last_packet_received = False
                    num_tries += 1

                    print "button press"

                    #set all digital out channels back low to avoid continuous button presses
                    dwf.FDwfDigitalIOOutputSet(self.interface_handler, c_uint16(0))

                # we have to manually stop sampling once packet_received_bit is raised
                curr_DIO = self._get_DIO_values()
                if ((curr_DIO & packet_received_bit) == packet_received_bit):
                    # packet received, stop sampling
                    dwf.FDwfDigitalInConfigure(self.interface_handler, c_bool(0), c_bool(0))

                    num_packets_received += 1
                    print "received packet {}".format(num_packets_received)
                    last_packet_received = True

                    # status check to make sure we're not sampling?
                    curr_status = self._get_DigitalIn_status()
                    print "current DigitalIn status: {}".format(curr_status)

                # get DigitalIn status because we want to read from file
                curr_status = self._get_DigitalIn_status(read_data=True)

                # record info about the data collection process (filling of the buffer)
                dwf.FDwfDigitalInStatusRecord(self.interface_handler, byref(cAvailable), byref(cLost), byref(cCorrupted))

                total_samples_lost += cLost.value
                total_samples_corrupted += cCorrupted.value

                cSamples += cLost.value

                if cSamples + cAvailable.value > nSamples:
                    cAvailable = c_int(nSamples - cSamples)

                #TODO: confirm that test harness measurements line up with software latency
                #print "available: {}, lost: {}, corrupted: {}".format(cAvailable.value, cLost.value, cCorrupted.value)
                # copy samples to rgwSamples on computer
                dwf.FDwfDigitalInStatusData(self.interface_handler, byref(rgwSamples, 2*cSamples), c_int(2*cAvailable.value))

                inner_loop_iterations += 1
                if last_packet_received == True:
                    break

                cSamples += cAvailable.value

            # reach here if packet was received OR if 1.5 million samples have been taken
            if last_packet_received == True:
                self.postprocess(num_packets_received, inner_loop_iterations, total_samples_lost, total_samples_corrupted, rgwSamples, bits_to_monitor, data_file)
            else:
                # we took 1.5 million samples and missed the packet
                num_packets_missed += 1
                # set last_packet_received to True to try button press again
                last_packet_received = True

            # clear rgwSamples for next packet
            rgwSamples = (c_uint16 * nSamples)()

        print "Done with experiment"

    def create_file(self):
        experiment_start_time = time.strftime("%H_%M_%S_%m_%d_%Y", time.localtime())
        print "starting dataset at {}".format(experiment_start_time)
        self.data_file = "data_" + experiment_start_time + ".csv"

    def _configure_DigitalIO(self):
        """configure the DigitalIO instrument for the experiment."""

        # this is to see that we can set DIO inputs/outputs according to the network inputs/outputs
        assert self.network_added == True

        # reset DigitalIO instrument
        dwf.FDwfDigitalIOReset()

        # enable AD DIO output channels (every channel that is not a network output channel) to be an output
        dwf.FDwfDigitalIOOutputEnableSet(self.interface_handler, c_int(self.output_channels_bit_rep))

        # set all enabled outputs to zero
        dwf.FDwfDigitalIOOutputSet(self.interface_handler, c_uint16(0))

        print "Configured DigitalIO."

    def _configure_DigitalIn(self, num_samples, trigger_channel_bit_rep):
        """configure DigitalIn instrument for the experiment.
        Samples at 1 MHz.
        Configures the trigger when the channel represented by trigger_channel_bit_rep is high.
        Configures instrument to take num_samples to take after trigger. 

        NOTE: both arguments are ints, not c_int()
        """

        #reset DigitalIn instrument
        dwf.FDwfDigitalInReset(self.interface_handler)

        # in record mode samples after trigger are acquired only
        dwf.FDwfDigitalInAcquisitionModeSet(self.interface_handler, acqmodeRecord)
        # set clock divider; we want to sample at 100 MHz / 100 = 1 MHz
        dwf.FDwfDigitalInDividerSet(self.interface_handler, c_int(100))
        # take 16 bits per sample
        dwf.FDwfDigitalInSampleFormatSet(self.interface_handler, c_int(16))

        # take num_samples after trigger
        dwf.FDwfDigitalInTriggerPositionSet(self.interface_handler, c_int(num_samples))
        # set trigger source to AD2 DigitalIn channels
        dwf.FDwfDigitalInTriggerSourceSet(self.interface_handler, trigsrcDetectorDigitalIn)
        # set DigitalIn trigger when trigger_channel_bit_rep is high
        dwf.FDwfDigitalInTriggerSet(self.interface_handler, c_int(0), c_int(trigger_channel_bit_rep), c_int(0), c_int(0))

        # start acquisition; should wait for trigger
        dwf.FDwfDigitalInConfigure(self.interface_handler, c_bool(0), c_bool(1))
        print "Configured DigitalIn.\n"

    def postprocess(self):


def initialize_receiving_mote(idx):
    """ Initializes and returns a Mote """
    print "         Mote {}:".format(idx)
    reception_channel = raw_input("             packet reception channel: ")
    assert <= reception_channel < 16

    return ReceiverMote(int(reception_channel))

def initialize_networks(num_netwokrs):
    """ Initializes all networks """

    receiving_motes = []
    packet_reception_channels = []

    for number in range(num_networks):
        print "Network {}:".format(number)
        num_motes = raw_input("    Number of receiving motes: ")

        for idx in range(num_motes):
            rx_mote = initialize_mote(idx)
            receiving_motes.append(rx_mote)
            packet_reception_channels.append(rx_mote.packet_reception_channel)

        button_press_confirmation = int(raw_input("    Button Press confirmation channel: "))
        assert 0 <= button_press_confirmation < 16

        creation_channel = int(raw_input("    Packet creation confirmation channel: "))
        assert 0 <= creation_channel < 16

        input_channel = int(raw_input("    Network input channels: "))
	    assert 0 <= input_channel < 16

        num_packets_to_send = input("   Number of packets to send: ")
        
        # create new network
        network = Network(num_motes, creation_channel, packet_reception_channels, input_channel, button_press_confirmation, num_packets_to_send)

        # add to global array of networks
        list_of_networks.append(network)

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

	num_networks = input("Number of networks: ")
	initialize_networks(num_networks)

	ad_utils = AnalogDiscoveryUtils()
	ad_utils.open_device()

	try:
		for network in list_of_networks:
			ad_utils.add_network(network)
			ad_utils.run(network)
	except KeyboardInterrupt:
		dwf.FDwfDigitalIOReset(ad_utils.interface_handler)
		ad_utils.close_device()
		sys.exit(1)

	ad_utils.close_device()
	sys.exit(0)

