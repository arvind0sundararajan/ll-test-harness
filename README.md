# ll-test-harness
Test harness to measure end-to-end latency in OpenWSN. Use in conjunction with [openwsn-ll].

[openwsn-ll]: https://github.com/arvind0sundararajan/openwsn-ll

## How to Use
For a one-to-one network, run `python acq.py acq_experiment_inputs.txt` in a Python 2.7 environment.

`acq.py` reads inputs from `acq_experiment_inputs.txt`, interfaces with the AnalogDiscovery2 (AD2), and writes raw data to `.csv` file in the `raw_data` folder.

`acq_experiment_inputs.txt` provides six inputs to `acq.py`.
1. AD2 channel for output signal confirmation (A)
2. AD2 channel for packet sent signal (B)
3. AD2 channel for packet reception signal (C)
4. AD2 channel for output (button press) signal (D)
5. Number of packets to send (E)
6. AD2 sampling frequency (F)

`acq_experiment_inputs.txt`:
``` #acq_experiment_inputs.txt
A, B, C
D
E
F
```

To process data from a `.csv` in `raw_data` directory, run `process_data.py` with the raw `.csv` file and a destination file as arguments. An example may look like this
```
$ python process_data.py /raw_data/YOUR_FILE.csv /processed_data/NEW_FILE
```
`process_data.py` automatically appends `.csv` to the destination file name. Processed data is in the form

| Packet number | Packet latency (ms) |
|---------------|---------------------|
|...            |...                  |
Latencies are accurate to 1 microsecond.
