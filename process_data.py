"""Converts the csv file outputted by the acquisition into a simpler csv with just packet and latency information.

Usage: python process_data.py [input_data_file] [desired output_data_file]
"""

import sys

def write_missed_packet_samples(output_data_file, missed_packets_samples):
	"""Missed_packets_samples is simply the same data array entered in by the test harness.
	Here we just move it to a new file for later analysis.
	The new file has the same title with missed_samples added to the end.
	"""
	print "writing missed packet samples to separate data file"
	missed_samples_data_file = output_data_file + "_missed_packet_samples"

	missed_packet_nums = []

	with open(missed_samples_data_file + ".csv", "a") as file:
		#title
		file.write("missed packet number, sample offset, latency (ms), sample\n")

		for sample_info in missed_packets_samples:
			#each element should be an array of strings
			file.write(sample_info[0] + ", " + sample_info[1] + ", " + sample_info[2] + ", " + sample_info[3] + "\n")
			curr_num = int(sample_info[0])
			if curr_num not in missed_packet_nums:
				missed_packet_nums.append(curr_num)

	print "finished writing missed packet samples to separate data file"
	print "test harness reported {} missed packets\nmissed packets:".format(len(missed_packet_nums))
	for i in missed_packet_nums:
		print -1 * i 
	return

def parse_data(input_data_file):
	"""Parses data in the format
	packet #, sample offset, latency (ms), (sample)
	save the last sample offset of every file.

	Returns an array where the first element is an array of all missed packet samples, 
	in the same format as the data input file.

	The second element is an array of arrays as follows:
	[[packet 1, packet 1 sample offset],
	 [packet 2, packet 2 sample offset],
	 ...
	 [packet n, packet n sample offset]
	]
	"""
	print "parsing input data"
	output_data = []
	missed_packets_data = []

	with open(input_data_file) as file:

		input_data = file.readlines()
		index = -1

		#start at packet 1
		prev_sample_info, curr_sample_info = [], []

		for line in input_data:
			index += 1
			if index == 0:
				# first line contains no data so we skip it
				continue

			#strip newline characters
			line = line.strip()
			# break up string into array of four strings
			line = line.split(", ")

			if index == 1:
				#initialize prev sample for index 1
				prev_sample_info = line
				continue

			curr_sample_info = line
			prev_packet_num = int(prev_sample_info[0])
			curr_packet_num = int(curr_sample_info[0])

			if curr_packet_num < 0:
				#supposed missed packet
				#add array of strings to array of missed samples data
				missed_packets_data.append(curr_sample_info)			

			if ((prev_packet_num != curr_packet_num) and prev_packet_num > 0):
				#save the previous sample's packet and its latency
				prev_packet_latency = float(prev_sample_info[2])
				output_data.append([prev_packet_num, prev_packet_latency])

			prev_sample_info = curr_sample_info

		#save the final packet if it was not missed
		prev_packet_num = int(prev_sample_info[0])
		if (prev_packet_num > 0):
			prev_packet_latency = float(prev_sample_info[2])
			output_data.append([prev_packet_num, prev_packet_latency])

	print "done parsing input data"
	return [missed_packets_data, output_data]

def write_new_data(output_data_file_str, data_to_write):
	"Takes the array of arrays from parse_data and writes data in the desired format."

	print "writing data to output file"

	missed_packet_samples_data = data_to_write[0]
	packet_latencies = data_to_write[1]

	if len(missed_packet_samples_data) != 0:
		write_missed_packet_samples(output_data_file_str, missed_packet_samples_data)

	with open(output_data_file_str + ".csv", 'a') as file:
		#omit headers because ipython notebook only wants ints and floats to parse.
		#file.write("Packet, Latency (ms)\n")

		for packet in packet_latencies:
			file.write("{}, {}\n".format(packet[0], packet[1]))

	print "finished writing data."
	return


if __name__ == "__main__":
	assert len(sys.argv) == 3

	input_data_file = sys.argv[1]
	output_data_file = sys.argv[2]

	data_to_write = parse_data(input_data_file)
	write_new_data(output_data_file, data_to_write)

	sys.exit(0)