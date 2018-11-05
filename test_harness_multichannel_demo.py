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

    def __init__(self, 
                 button_press_channel_1,
                 button_press_channel_2, 
                 button_press_mirror_channel_1, 
                 button_press_mirror_channel_2,
                 packet_created_channel, 
                 packet_received_channels_1 = [],
                 packet_received_channels_2 =[],
                 killswitch_channel =None,
                 config_dict = None):

        self.ad2 = AnalogDiscoveryUtils()
        self.button_press_bit_mask = (1<<button_press_channel_1) | (1<<button_press_channel_2) 

        self.button_press_mirror_bit_mask = (1<<button_press_mirror_channel_1) | (1<<(button_press_mirror_channel_2))
        self.packet_created_bit_mask = (1<<packet_created_channel)

        self.packet_received_bit_mask_1 = 0

        for channel in packet_received_channels_1:

            self.packet_received_bit_mask_1 |= (1<<channel) 

        self.packet_received_bit_mask_2 = 0

        for channel in packet_received_channels_2:

            self.packet_received_bit_mask_2 |= (1<<channel) 

        print "{0:16b}".format(self.packet_received_bit_mask_1)
        print "{0:16b}".format(self.packet_received_bit_mask_2)

        #list comprehension for packet received channels
        self.packet_received_channels_1 = [(1<<channel) for channel in packet_received_channels_1 ]
        self.packet_received_channels_2 =[(1<<channel) for channel in packet_received_channels_2 ]

        print self.packet_received_channels_1
        print self.packet_received_channels_2
        self.packet_latencies = {}
        self.killswitch_mask = (1<<killswitch_channel)
        #self.channel_1 = packet_received_channel
        #self.channel_2 = packet_received_channel_2
        self.sampling_freq = -1

        ###config dict based code
        self.packet_received_masks = {}
        self.packet_received_channel_masks = {}
        self.button_press_bit_mask = 0
        self.button_press_mirror_bit_masks = {} 

        for mote_key in config_dict.keys():
            self.button_press_bit_mask |= (1 << config_dict[mote_key]["press_channel"])

            #only have one button press mirror trigger
            self.button_press_mirror_bit_mask = config_dict[mote_key]["mirror_channel"]

            #iterate through each packet rx channel to build rx mask
            self.packet_received_masks[mote_key] = 0
            self.packet_received_channel_masks[mote_key] = {}
            for channel in config_dict[mote_key]["rx_channels"]:
                self.packet_received_masks[mote_key] |= (1<<channel)
                self.packet_received_channel_masks[mote_key][channel] = (1<<channel)  

            
            
            
            

        print bin(self.button_press_bit_mask)
        print self.packet_received_masks
        print self.packet_received_channel_masks
        print bin(self.button_press_mirror_bit_mask)
        print self.button_press_mirror_bit_mask
        self.config_dict = config_dict

    def write_data_to_file(self, file_to_write, mote_key):
        with open(file_to_write +mote_key +".csv", "a") as f:
            header_string = "Packet, "

            for latency_num in range(1,len(self.packet_latencies[mote_key][0])):
                header_string += 'Latency {} (ms), '.format(i)

            header_string +="Minimum Latency\n"
            f.write(header_string)

            i = 1
            
            for latencies in self.packet_latencies[mote_key]:
                write_string = "{}".format(i)
                for rx_latency in latencies:
                    write_string += "{}, ".format(rx_latency)

                f.write(write_string + "\n")
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

    def postprocess(self, array_of_samples, steady_state_DIO,sample_rate,packet_num,data_dir_name, mote_key):
        """Postprocesses the array of samples to return the latency of this packet.
        Corresponds to the first sample offset which shows a difference in the packet received channel.
        """
        #print 'Postprocessing.'

        #loop through each mote
        packet_received_bit_mask = self.packet_received_masks[mote_key] #total bitpacked representation of all channels being used for rx
        packet_received_initial_state = steady_state_DIO & packet_received_bit_mask
        packet_received_channels = self.packet_received_channel_masks[mote_key] #dict of channels and their bit-packed form 
        packet_received_bools = {} #dict of channels and whether or not a packet was received on that channel
        latency_dict = {}

        for channel in packet_received_channels.keys():
            packet_received_bools[channel] = False
            latency_dict[channel] = 0


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


            for channel, channel_bits in packet_received_channels.iteritems():
                if (sample & channel_bits) != (packet_received_initial_state & channel_bits):
                    #block is first entered for first sample offset where pin changed state
                    if packet_received_bools[channel] == False:
                        #latency = (i / 100.0)
                        latency_dict[channel] = (i / float(sample_rate))
                        packet_received_bools[channel] = True
                        
                        #set overall packet_received to true 
                        if packet_received == False:
                            packet_received = True
                            min_latency = latency_dict[channel]

                    
    
            if( False not in packet_received_bools.values()):
                break           

            """
            if ((sample & self.packet_created_channel) == (steady_state_DIO & self.packet_created_channel)) and packet_received:
                ack_missed = False
                break
            """
            



        if ( (latency1 < 0.7 and latency1>0) or (latency2 < 0.7 and latency2>0) or (latency1 < 1.4 and latency1>0.9) or (latency2 < 1.4 and latency2>0.9)):
            self.write_anomoly_data_to_file(str(packet_num),array_of_samples,data_dir_name+".csv",False)
        if debounce_reject:
            self.write_anomoly_data_to_file(str(packet_num),array_of_samples,data_dir_name + ".csv",True)
            debounce_reject = False
        
        latency_array = [latency for latency in latency_dict.values()]
        latency_array.append(min_latency)
        return latency_array


    def run(self, num_packets,sample_length):
        #main loop of experiment
        experiment_start_time = time.strftime("%H_%M_%S_%m_%d_%Y", time.localtime())
        print "starting dataset at {}\n".format(experiment_start_time)
        data_file_prefix = experiment_start_time 

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
            wait = 100
            time.sleep(wait * 0.001)
            #turn off killswitch to allow resends to happen
            self.ad2.button_depress()

            #get initial state of DIO pins
            steady_state_DIO = self.ad2.get_DIO_values()
            #press button
            self.ad2.button_press(self.button_press_bit_mask)
            #print "button pressed"

            for mote_key in self.config_dict.keys():
                self.packet_latencies[mote_key] = []

            while True:
                self.ad2.dwf.FDwfDigitalInStatus(self.ad2.interface_handler, c_int(1), byref(sts))
                #if sts.value !=1:
                    #print "STS VAL: " + str(sts.value)
                #print stsDone.value
                if sts.value == stsDone.value:
                    #print "Done sampling."
                    break
                #print "before getting dio values"
                curr_DIO_values = self.ad2.get_DIO_values()
                #print "curr_DIO_values: {}".format(binary_num_str(curr_DIO_values))
                #if (((curr_DIO_values ^ steady_state_DIO) & self.packet_received_bit_mask) != 0) and not packet_received:
                    #print "curr_DIO_values: {}".format(binary_num_str(curr_DIO_values))
                    # packet received
                    #print "Pkt received"
                 #   packet_received = True  #why is this here? i don't think i need this anymore 


            self.ad2.button_depress()

            self.ad2.read_buffer(rgwSamples)
            self.ad2.button_press(self.killswitch_mask)

            curr_latencies = {} 
            print_string = "{} ".format(i+1)

            for mote_key in self.config_dict.keys():
                curr_latencies[mote_key] = self.postprocess(rgwSamples, steady_state_DIO,sample_rate,i,data_file_prefix,mote_key)

                mote_string = ""
                #loop through all latencies and build print string
                for latency in curr_latencies[mote_key]:
                    mote_string += "{:.5f} ".format(latency)

                print_string += "{}: ".format(mote_key) + mote_string + ", "

                self.packet_latencies[mote_key].append(curr_latencies[mote_key])
                #self.write_data_to_file(data_file_prefix,mote_key)

            print print_string


        self.ad2.close_device()

        for mote_key in self.packet_latencies.keys:
            self.write_data_to_file(data_file_prefix,mote_key)

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
        self.dwf.FDwfDigitalInDividerSet(self.interface_handler, c_int(sample_divider))     # 16bit per sample format
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
    my_experiment = Experiment(button_press_channel_1 = 0,
                               button_press_channel_2 = 5, 
                               button_press_mirror_channel_1 = 1, 
                               button_press_mirror_channel_2 = 6,
                               packet_created_channel = 15, 
                               packet_received_channels_1 = [2,3,4],
                               packet_received_channels_2 =[7,8,9],
                               killswitch_channel =14,
                               config_dict = {
                                               "mote0" :  {
                                                            "press_channel" : 0,
                                                            "mirror_channel" : 1,
                                                            "rx_channels" : [2,3,4],
                                                          },

                                               "mote1" :  {
                                                            "press_channel" : 5,
                                                            "mirror_channel" : 1,
                                                            "rx_channels" : [7,8,9]
                                                          }
                                                }
                                )
    sample_length = 10 #length of time you want to sample for in ms
    try:
        my_experiment.run(1000,sample_length)

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
