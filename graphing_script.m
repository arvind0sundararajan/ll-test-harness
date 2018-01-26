path = "processed_data/one_to_one/";
file = "5_active_slots/10k_5as_2.csv";
latencies = csvread(path+file);
latencies = latencies(:,2);
histogram(latencies,'BinWidth',1);