path = "data/";
file = "10k_5as_1_1/10k_5as_1_1.csv";
latencies = csvread(path+file);
latencies = latencies(:,2);
histogram(latencies,'BinWidth',1);