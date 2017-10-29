"""
    Latency recording script for one-to-many WSN
    interfaces with AnalogDiscovery2 to trigger button press and read mote pins.

    User inputs:
        1. AD2 button press channel
        2. Tx mote button press mirror channel, Tx mote packet creation channel
        3. Rx mote 1 reception channel, Rx mote 2 reception channel, ...
        4. Number of packets
        5. Sampling frequency

    Output:
        1. Records data to [FILENAME].csv

    Written by Alex Yang and Arvind Sundararajan
    10/27/2017.
"""

from ctypes import *
from dwfconstants import *
import sys
import time

dwf = None
# list of networks
list_of_networks = []

class Network:
    button_press_channel = 0
    mirror_channel = 0
    creation_channel = 0
    reception_channels = []
    num_packets = 0

    def __init__(self, button_press_channel, mirror_channel, creation_channel, reception_channels, num_packets_to_send):
        self.button_press_channel = button_press_mirror_channel
        self.mirror_channel = mirror_channel
        self.creation_channel = creation_channel
        self.reception_channels = reception_channels
        self.num_packets = num_packets_to_send

class AnalogDiscoveryUtils:

    def __init__(self, sampling_freq_user_input):
        self.interface_handler = None

        self.internal_clock_freq = 0
        self.sampling_freq = sampling_freq_user_input
        self.period_ms = (1000.0 / self.sampling_freq)

        self.num_packets_experiment = -1

        # bit representations of the AD2 DIO channels
        # index is 1 if that pin is included in input/output
        self.input_channels_bit_rep = -1
        self.output_channels_bit_rep = -1

        # relevant bits of AD output
        self.button_press_pos = -1
        self.button_press_bit = -1

        #relevant bits and bit positions of AD inputs
        # note that button_press_mirror_bit is an AD input while button_press_bit is an AD output
        self.button_press_mirror_pos = -1
        self.button_press_mirror_bit = -1

        self.packet_created_pos = -1
        self.packet_created_bit = -1

        self.packet_received_pos = -1
        self.packet_received_bit = -1

        # when post-processing we only care about changes to these bits
        self.bits_to_monitor = -1
        self.num_channels_to_monitor = -1

        # boolean that keeps track of AD2's DIO interface with network
        self.network_added = False

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

        if hdwf.value == 0:
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

    def add_network(self, network):
        """sets network outputs to be AD2 input channels
        sets all other AD2 channels to be outputs. 
        this is done to control AD2 outputs and keep them constant
        """     
        self.num_packets_experiment = network.num_packets

        # relevant bits of AD output
        self.button_press_pos = network.input_channels[0]
        self.button_press_bit = 1 << self.button_press_pos

        #relevant bits and bit positions of AD inputs
        # note that button_press_mirror_bit is an AD input while button_press_bit is an AD output
        self.button_press_mirror_pos = network.output_channels[0]
        self.button_press_mirror_bit = 1 << self.button_press_mirror_pos

        self.packet_created_pos = network.output_channels[1]
        self.packet_created_bit = 1 << self.packet_created_pos

        self.packet_received_pos = network.output_channels[-1]
        self.packet_received_bit = 1 << self.packet_received_pos

        # when post-processing we only care about changes to these bits
        self.bits_to_monitor = self.button_press_mirror_bit | self.packet_created_bit | self.packet_received_bit
        self.num_channels_to_monitor = len(network.output_channels)

        self.input_channels_bit_rep = self.bits_to_monitor

        # every channel that is not a network input channel is an AD output
        self.output_channels_bit_rep = ((2 ** 16) - 1) ^ self.input_channels_bit_rep

        self.network_added = True

        print "button_press_bit: {}".format(binary_num_str(self.button_press_bit))
        print "button_press_mirror_bit: {}".format(binary_num_str(self.button_press_mirror_bit))
        print "packet_created_bit: {}".format(binary_num_str(self.packet_created_bit))
        print "packet_received_bit: {}".format(binary_num_str(self.packet_received_bit))
        print "bits_to_monitor: {}\n".format(binary_num_str(self.bits_to_monitor))

        #print AD2 output and input channels
        print "AD2 enabled outputs: {}".format(binary_num_str(self.output_channels_bit_rep))
        print "AD2 inputs: {}\n".format(binary_num_str(self.input_channels_bit_rep))    

    def _get_DIO_values(self, print_vals=False):
        """Returns an int containing the DIO channel values.
        """
        dio_pins = c_uint16()
        # fetch digital IO information from the device
        dwf.FDwfDigitalIOStatus(self.interface_handler)
        # read state of all pins, regardless of output enable
        dwf.FDwfDigitalIOInputStatus(self.interface_handler, byref(dio_pins))
        if print_vals:
            print "Digital IO Pins:  " + binary_num_str(dio_pins.value) + "\n"
        return dio_pins.value

    def _configure_DigitalIO(self):
        """configure the DigitalIO instrument for the experiment."""

        # this is to see that we can set DIO inputs/outputs according to the network inputs/outputs
        assert self.network_added == True

        # reset DigitalIO instrument
        dwf.FDwfDigitalIOReset()

        # enable AD DIO output channels (every channel that is not a network output channel) to be an output
        dwf.FDwfDigitalIOOutputEnableSet(self.interface_handler, c_int(self.output_channels_bit_rep))

        #enabled_outputs = c_uint32()
        #dwf.FDwfDigitalIOOutputEnableGet(self.interface_handler, byref(enabled_outputs))
        #print enabled DIO outputs as bitfield (32 digits, removing 0b at the front)
        #print "enabled digital output pins:  " + bin(enabled_outputs.value)[2:]

        # set all enabled outputs to 1 except button press bit
        dwf.FDwfDigitalIOOutputSet(self.interface_handler, c_uint16(~self.button_press_bit))

        #print "Configured DigitalIO."
        return c_uint16(~self.button_press_bit)


    def _configure_DigitalIn(self, num_samples, trigger_channel_bit_rep):
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
        # set DigitalIn trigger when trigger_channel_bit_rep is high
        dwf.FDwfDigitalInTriggerSet(self.interface_handler, c_int(0), c_int(trigger_channel_bit_rep), c_int(0), c_int(0))

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
    
    def _copy_buffer_samples(self, buffer_info, nSamples, arr, last_read=False):
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

        cSamples += cLost.value
        if cSamples + cAvailable.value > nSamples:
            cAvailable = c_int(nSamples - cSamples)

        # copy samples to arr on computer
        dwf.FDwfDigitalInStatusData(self.interface_handler, byref(arr, 2*cSamples), c_int(2*cAvailable.value))

        if (last_read == False):
            cSamples += cAvailable.value

        buffer_info = [cSamples, buffer_info[1] + cLost.value, buffer_info[2] + cCorrupted.value]
        return buffer_info

    def run(self):
        """The main function of the experiment.
        Our test harness consists of two parts:
            -digital output to trigger openmote pin. the output rising edge is 1 ms after the reception is high
            -logic analyzer to sample input channels to AD, and save values to a csv file.
            Script workflow:
            (Python): trigger rising edge on DIO 0.
            (AD2): start sampling at 1 MHz. sample until packet received rising edge. stop sampling.
            (Python): continuously copy samples (contents of buffer) to memory. 
            once packet is received:
            (Python) postprocess: remove redundant samples (only save samples that change 0-1)
            (Python): write these samples to file
            (Python): increment number of packets sent
            repeat above steps until number of packets sent = number of packets in experiment
        """
        run_start_timestamp = time.clock()
        experiment_start_time = time.strftime("%H_%M_%S_%m_%d_%Y", time.localtime())
        print "starting dataset at {}\n".format(experiment_start_time)
        data_file = "data/data_" + experiment_start_time + ".csv"
        with open(data_file, 'a') as f:
            f.write("Packet, Sample offset, Latency (ms), [packet_received_bit][packet_created_bit][button_press_mirror_bit]\n")

        ##### EXPERIMENT SETUP #####
        # sample for a max of 1.5 seconds
        # approximate number of samples assuming ~500ms latency per packet
        nSamples = (int) (1.5 * self.sampling_freq)

        num_packets_received = 0
        num_packets_missed = 0

        # array to hold indices of packets missed
        packet_number_missed = []

        # num_packets_received + num_packets_missed must equal num_tries
        num_tries = 0
        
        # ready for next button press if previous packet has been handled
        # and if instruments, variables are configured for next packet
        last_packet_handled = True
        # keep track of if current packet has been received
        packet_received = True
        ##### END SETUP #####

        ##### MAIN LOOP of experiment. #####
        # runs for the duration of the experiment
        #note: openmote toggles its pins every packet creation and reception

        while num_packets_received < self.num_packets_experiment:
            #csamples, lost, corrupted
            buffer_info = [0, 0, 0]

            # clear rgwSamples for next packet
            rgwSamples = (c_uint16 * nSamples)()

            # reset and configure DigitalIO
            steady_state_DIO = self._configure_DigitalIO()

            # reset and configure DigitalIn to take nSamples on trigger
            # set DigitalIn trigger when button_press_mirror_bit channel is raised (this should start sampling)
            self._configure_DigitalIn(nSamples, self.button_press_mirror_bit)


            ready_for_next_button_press = True

            #print "begin acquisition {}".format(num_tries + 1)

            buffer_flush_start, buffer_flush_stop = 0, 0
            # inner loop: runs from button press until packet received.
            while buffer_info[0] < nSamples:
                if ((last_packet_handled == True) and (ready_for_next_button_press == True)):
                    # we can send the next packet because the last packet was handled (received or understood to be missed)
                    # and instruments are configured
                    # button press -> set value on enabled AD2 output pins (digital_out_channels_bits)
                    # AD2 output is hard wired to button press input which triggers acquisition

                    #get current value of packet_received_pin; when packet is received this will toggle
                    curr_DIO = self._get_DIO_values()
                    packet_received_pin_state = curr_DIO & self.packet_received_bit

                    last_packet_handled = False
                    ready_for_next_button_press = False
                    packet_received = False

                    # press the button. all other outputs go low.
                    dwf.FDwfDigitalIOOutputSet(self.interface_handler, c_uint16(self.button_press_bit))
                    #reset all enabled digital out channels back to steady state (all high except button press)
                    dwf.FDwfDigitalIOOutputSet(self.interface_handler, steady_state_DIO)
                    #print "button pressed"

                    num_tries += 1


                #buffer_flush_start = time.clock()
                #print "{} ms between buffer reads".format((buffer_flush_start - buffer_flush_stop)*1000)
                # copy buffer samples to memory and flush
                buffer_info = self._copy_buffer_samples(buffer_info, nSamples, rgwSamples)
                #buffer_flush_stop = time.clock()

                #print "buffer read took {} ms".format((buffer_flush_stop - buffer_flush_start)*1000)

                # manually stop sampling once packet_received_bit is not equal to its pin state
                curr_DIO = self._get_DIO_values()
                if ((curr_DIO & self.packet_received_bit) != packet_received_pin_state):
                    # packet_received_bit toggled 
                    # packet received, stop sampling
                    dwf.FDwfDigitalInConfigure(self.interface_handler, c_bool(0), c_bool(0))

                    packet_received = True
                    num_packets_received += 1
                    #print "received packet {}".format(num_tries)

                    #copy last buffer samples to memory
                    buffer_info = self._copy_buffer_samples(buffer_info, nSamples, rgwSamples, last_read=True)
                    break

            # reach here if packet was received OR if 1.5 million samples have been taken
            if packet_received == True:
                self.postprocess(num_tries, buffer_info, rgwSamples, data_file)
                last_packet_handled = True
            else:
                # we took 1.5 million samples and supposedly missed the packet
                num_packets_missed += 1
                packet_number_missed.append(num_tries)
                self.postprocess(num_tries, buffer_info, rgwSamples, data_file, missed_packet=True)
                # set last_packet_handled to True to try button press again
                last_packet_handled = True

        run_end_timestamp = time.clock()
        print "Done with experiment"
        #print all packets sent, lost, total info
        print "Number of tries: {}".format(num_tries)
        print "Number of received packets: {}".format(num_packets_received)
        print "Number of missed packets: {}\n".format(num_packets_missed)
        print "Total duration: {} seconds".format(run_end_timestamp - run_start_timestamp)
        return

    def postprocess(self, attempt_number, buffer_info, data, data_file, missed_packet=False):
        """Only write a sample to the data file if any of the DIO bits change.
        
        The data saved is an integer with ith bit = 1 if ith channel was high, bit = 0 if channel was low
        data format: packet #, sample offset, latency (ms), XYZ (sample)

        If test harness thinks it's a missed packet, we still postprocess and write all the samples to the buffer for later analysis.
        In order for the data processing script to discern packets that the test harness thinks are missed:
            instead of writing attempt_number in the first column, we write -attempt_number.
        """
        #print "postprocessing {}".format(packet_number)

        pp_start = time.clock()
        if missed_packet:
            print "supposedly missed packet {}".format(attempt_number)
            attempt_number = -1 * attempt_number

        with open(data_file, 'a') as f:
            # postprocessing
            index, prev_sample, latency = 0, 0, 0
            for sample in data:
                if (index > buffer_info[0]) and (not missed_packet):
                    # we want to check every sample if test harness thinks packet was missed
                    break

                if (prev_sample ^ sample) != 0:
                #if ((prev_sample ^ sample) & self.bits_to_monitor) != 0:
                    # one or more of the bits to monitor have changed

                    #TODO: add check to see if sample is weird. every output bit other than button press must always be high.
                    #sample_output_str = str(get_bit(sample, self.packet_received_pos))
                    #sample_output_str += str(get_bit(sample, self.packet_created_pos))
                    #sample_output_str += str(get_bit(sample,  self.button_press_mirror_pos))
                    sample_output_str = binary_num_str(sample, split=True)
                    latency = index * self.period_ms
                    f.write("{}, {}, {}, {}\n".format(attempt_number, index, latency, sample_output_str))

                index += 1
                prev_sample = sample

        pp_stop = time.clock()
        if missed_packet:
            print "postprocessing took {} seconds".format(pp_stop - pp_start)
        else:       
            print "{}  {}".format(attempt_number, latency)
        #print "cSamples: {}, cLost: {}, cCorrupted: {}".format(buffer_info[0], buffer_info[1], buffer_info[2])
        #print "took {} samples for packet {}".format(index, packet_number)
        #print "postprocessing took {} seconds".format(pp_stop - pp_start)
        #print "\n"
        return

    def test(self):
        """Miscellaneous testing."""
        self._configure_DigitalIO()

        enabled_outputs = c_uint32()

        dwf.FDwfDigitalIOOutputEnableGet(self.interface_handler, byref(enabled_outputs))
        #print enabled DIO outputs as bitfield (32 digits, removing 0b at the front)
        print "enabled digital output pins:  " + bin(enabled_outputs.value)[2:].zfill(32)

        print "outputting on every output"
        for i in range(16):
            output = c_uint16(1<<i)
            dwf.FDwfDigitalIOOutputSet(self.interface_handler, output)
            self._get_DIO_values(print_vals=True) 
        return

def get_bit(num, position):
    """Get the bit located at [position] in [num]
    """
    return (num >> position) & 0b1

def get_bit_positions(bit_mask):
    """Return an array of positions for each enabled bit in bit_mask."""
    bit_positions = []
    # find bit positions of enabled bits in mask
    for i in range(16):
        if (bit_mask & (1 << i)) != 0:
            bit_positions.append(i)
    return bit_positions

def concatenate_bits(num, bit_mask):
    """For each bit that is set in bit_mask, concatenate the bits in those positions in num.
    Example: num = 0b101010, bit_mask = 0b110101 -> return 0b1000
    Assume num, bit_mask are 16 bits.
    """
    bit_positions = get_bit_positions(bit_mask)
    num_bits_at_positions = [get_bit(num, pos) for pos in bit_positions]
    out = 0
    for bit in num_bits_at_positions:
        out = (out << 1) | bit
    return out

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

def initialize_network(button_press_channel, mirror_channel, creation_channel, reception_channels, num_packets_to_send):
    """ Initializes a network. """

    assert 0 <= button_press_channel < 16
    assert 0 <= mirror_channel < 16
    assert 0 <= creation_channel < 16
    for ch in reception_channels:
        assert 0 <= ch < 16

    # create new network
    network = Network(button_press_channel, mirror_channel, creation_channel, reception_channels, num_packets_to_send)

    # add to global array of networks
    list_of_networks.append(network)
    return

if __name__ == "__main__":
    ### Parse input to initialize variables ###
    file_input_format_info = "Input file format:\n"
    file_input_format_info += "[button press channel]\n"
    file_input_format_info += "[button press mirror channel], [packet creation channel]\n"
    file_input_format_info += "[packet reception channel 1], [packet reception channel 2], ...\n"
    file_input_format_info += "[number of packets to send]\n"
    file_input_format_info += "[sampling frequency]\n\n"

    assert len(sys.argv) == 2
    input_file = sys.argv[1]

    with open(input_file) as file:
        params = file.readlines()
    #remove whitespace characters in each line
    params = [line.strip() for line in params]
    #convert string of comma separated ints to list of ints
    params = [[int(i) for i in line.split(", ")] for line in params]

    button_press_channel = params[0][0]
    button_press_mirror_channel = params[1][0]
    packet_creation_channel = params[1][1]
    packet_reception_channels = params[2]
    num_packets_to_send = params[3][0]
    sampling_freq_user_input = params[4][0]

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

    initialize_network(button_press_channel, button_press_mirror_channel, packet_creation_channel, packet_reception_channels, num_packets_to_send)

    ad_utils = AnalogDiscoveryUtils(sampling_freq_user_input)
    ad_utils.open_device()

    try:
        for network in list_of_networks:
            ad_utils.add_network(network)
            ad_utils.run()
    except KeyboardInterrupt:
        dwf.FDwfDigitalIOReset(ad_utils.interface_handler)
        ad_utils.close_device()
        sys.exit(1)

    ad_utils.close_device()
    sys.exit(0)