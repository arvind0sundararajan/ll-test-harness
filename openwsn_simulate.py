import numpy as np
import matplotlib.pyplot as plt

print("top-level")
pdr = 0.9
slotframe_slots = 11
slot_ms = 10
num_retries = 5
latencies = []
missed_packets = 0

def simulate(num_packets, active_slots):
	global missed_packets
	asn = -1
	while num_packets > 0:
		latency = 0
		tries_remaining = num_retries + 1

		while tries_remaining > 0:
			asn = asn + 1
			latency = latency + slot_ms
			if asn % slotframe_slots < active_slots:
				latency = latency + np.random.random_integers(-5, 5)
				pkt_received = np.random.random() < pdr
				if pkt_received:
					latencies.append(latency)
					num_packets = num_packets - 1
					break
				else:
					tries_remaining = tries_remaining - 1

		if not tries_remaining:
			missed_packets = missed_packets + 1

if __name__ == "__main__":
	num_packets = int(input("num of pkts: "))
	active_slots = int(input("active slots: "))
	simulate(num_packets, active_slots)

	print("Missed packets: {}".format(missed_packets))
	print("Max latency: {}".format(max(latencies)))
	bins = range(0, 100, 10)
	plt.figure("Figure 11")
	plt.hist(latencies, bins=bins)
	plt.show(block=True)

