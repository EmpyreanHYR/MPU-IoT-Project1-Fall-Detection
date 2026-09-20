# Public edge and delivery evidence

`summary.json` contains the measured Raspberry Pi deployment and cloud-delivery results used in the English presentation.

- Paired timing: same YOLOv8s-pose input, four videos replayed twice per backend; five warm-up frames excluded. Throughput includes decode, pose, temporal classification and record writes, excluding initialization.
- Synthetic classification: 20 fall and 20 non-fall clips sampled before inference. Clip prediction is the maximum valid window probability at threshold 0.5. One negative clip has no output and remains a separate column.
- Stability: a 603.8-second offline replay. Memory, temperature and record counts describe this session only.
- Persistence: all 100 committed writes recovered after forced writer termination.
- Delivery: all 85 tested records matched. Replaying 34 records after cloud service restart produced no duplicate insertion. A 30-second upload-path outage retained 17 records; polling first observed zero pending at 2.8278 seconds after recovery.
- Connected latency: all 34 sorted values are included. The interval starts at capture of the last source frame in a classification window and ends at cloud receipt. It is not fall-onset-to-alert latency.

The public export omits credentials, host addresses, local filesystem paths, raw video, record/device identifiers and absolute event timestamps. It contains observed aggregate evidence and delivery intervals, not a simulated cloud service.
