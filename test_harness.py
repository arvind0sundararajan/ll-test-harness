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

  # generate on DIO-0 1Mhz pulse (100MHz/25/(3+1)), 25% duty (3low 1high)
  #dwf.FDwfDigitalOutEnableSet(hdwf, c_int(i), c_int(1))
  #dwf.FDwfDigitalOutDividerSet(hdwf, c_int(i), c_int(25))
  #dwf.FDwfDigitalOutCounterSet(hdwf, c_int(i), c_int(3), c_int(1))
      
  # generate counter
  """
  for i in range(0, 16):
      dwf.FDwfDigitalOutEnableSet(hdwf, c_int(i), c_int(1))
      dwf.FDwfDigitalOutDividerSet(hdwf, c_int(i), c_int(1<<i))
      dwf.FDwfDigitalOutCounterSet(hdwf, c_int(i), c_int(1), c_int(1))

  dwf.FDwfDigitalOutConfigure(hdwf, c_int(1))
  """

  #sample rate = system frequency / divider, 100MHz/1
  dwf.FDwfDigitalInDividerSet(hdwf, c_int(50000))
  # 16bit per sample format
  dwf.FDwfDigitalInSampleFormatSet(hdwf, c_int(16))
  # set number of sample to acquire
  cSamples = 4096
  rgwSamples = (c_uint16*cSamples)()
  dwf.FDwfDigitalInBufferSizeSet(hdwf, c_int(cSamples))


  dwf.FDwfDigitalInTriggerSourceSet(hdwf, c_ubyte(3)) # trigsrcDetectorDigitalIn
  dwf.FDwfDigitalInTriggerPositionSet(hdwf, c_int(cSamples))
  dwf.FDwfDigitalInTriggerSet(hdwf, c_int(0), c_int(0), c_int(1), c_int(0)) # DIO0 rising

  # begin acquisition
  dwf.FDwfDigitalInConfigure(hdwf, c_bool(0), c_bool(1))
  print "   waiting to finish"

  while True:
      dwf.FDwfDigitalInStatus(hdwf, c_int(1), byref(sts))
      print "STS VAL: " + str(sts.value)
      if sts.value == stsDone.value :
          break
      time.sleep(1)
  print "Acquisition finished"

  # get samples, byte size
  dwf.FDwfDigitalInStatusData(hdwf, rgwSamples, 2*cSamples)
  dwf.FDwfDeviceCloseAll()

  with open("test_sampling.csv", "a") as data_file:
    data_file.write("Sample offset, Sample\n")

    i = 0
    for sample in rgwSamples:
        data_file.write("{}, {}\n".format(i, binary_num_str(rgwSamples[i], split=True)))
        i += 1


