# FallGuard speaker manuscript

Twelve sections for a 7–8 minute talk, followed by the live demonstration and questions.

## Speaker notes · 30 seconds

Our project is FallGuard, a camera-based fall-detection prototype. We study how to classify short pose sequences when observations are incomplete, then deploy the full inference pipeline on a Raspberry Pi. The device extracts poses, classifies motion and stores records without an Internet connection. A Hailo accelerator makes pose extraction faster. When the connection returns, the cloud receives the saved records. I will cover the model, its evaluation, the deployment results and our demonstration.

---

## Speaker notes · 35 seconds

The difficulty is that falls and ordinary activities can share similar postures. Motion before and after a posture change helps distinguish them. Recent studies combine temporal convolutions, attention or state-space models. Other work incorporates skeleton geometry and confidence. We focus on incomplete pose observations and use a short buffered sequence. The care scenario also introduces a system requirement: losing the network should not stop local detection or erase the event history.

---

## Speaker notes · 40 seconds

The final system has four local stages. A camera or local video provides frames. Hailo extracts human poses, and the Pi CPU runs MaskedBiMamba on a one-second window. The device updates its alert state and saves records in SQLite. A separate local page lets the operator see this without a network. The cloud is responsible for centralized history and event review. It acknowledges records after storage, which lets the device retry an interrupted transfer without creating duplicates. This extends our original plan, which assigned classification to the cloud.

---

## Speaker notes · 50 seconds

The input contains twelve body joints. For every joint we retain normalized x and y coordinates and confidence. We first mask some training frames, embed the sequence, and apply temporal attention. Independent forward and backward Mamba branches then process the buffered window. Their outputs are aligned and fused. Finally, a learned quality gate weights each frame before classification. Its inputs are mean joint confidence, the visible-joint fraction and person confidence. We reuse the Mamba operator; our contribution is the combined architecture and its evaluation. The ablations will show which parts actually help.

---

## Speaker notes · 40 seconds

Our primary study combines CAUCAFall and GMDCSA-24, with fourteen subject groups. We use four subject-disjoint folds and three seeds, so each model has twelve evaluations. Le2i has a separate baseline experiment and is also held out for external evaluation. The edge sample contains forty synthetic clips. These protocols should not be pooled. We report window, video and event measures because a strong score at one level can hide problems at another. The false-alarm rate uses the evaluated video intervals, rather than a full day of continuous monitoring.

---

## Speaker notes · 40 seconds

The model ranking depends on the metric. The Transformer encoder leads clean window F1 and event recall. MaskedBiMamba has the highest window precision and the lowest unmatched-event rate, with video F1 close to the Transformer. This is a trade-off, not an across-the-board improvement. The absolute false-alarm rate is still high. For a monitoring system, fewer false notifications only help if the associated loss in sensitivity is acceptable. The metric selector lets us inspect that trade-off directly.

---

## Speaker notes · 35 seconds

We evaluated ten variants across the same folds and seeds. Removing the backward branch or temporal attention reduces window F1 and increases false alarms. These results support their role in the combined model. The other components are less uniform: removing masking improves clean window F1, and removing quality pooling improves clean video F1. We therefore describe them as controls over the operating point, rather than claiming that every component improves every metric.

---

## Speaker notes · 40 seconds

The clearest advantage appears under missing frames. At thirty percent frame removal, MaskedBiMamba retains a window F1 of 0.6276, compared with 0.4361 for TCNTE. The pattern also appears on external Le2i data. Neighboring observations provide temporal information that can compensate for some missing frames. Removing joints is harder because it removes body geometry throughout a sequence. These are controlled perturbations of extracted poses, so they do not establish robustness to every camera or lighting condition.

---

## Speaker notes · 45 seconds

The Pi test runs the complete pipeline with no external network interface or route. In the paired timing test, both backends use YOLOv8s-pose. Hailo raises throughput from 1.73 to 20.56 frames per second, about 11.9 times faster. The classifier still runs on the Pi CPU. On forty synthetic clips, thirty-nine produce an output. There are twenty true positives, eleven true negatives and eight false positives. A positive prediction anywhere in a clip is easier than detecting the annotated fall itself, so we also report that only fourteen positive clips are detected within that interval.

---

## Speaker notes · 40 seconds

We also tested what happens around interruptions. During a thirty-second upload-path outage, seventeen records remain on the Pi. The queue is observed empty 2.83 seconds after the path is restored. Across the delivery tests, all eighty-five records match their edge identifiers and original capture times. Replaying records after a cloud restart creates no duplicates. Separately, all one hundred committed writes survive forced writer termination. A ten-minute offline replay processes over eleven thousand frames without reported throttling. These are measured recovery results, not simulated network animations.

---

## Speaker notes · 35 seconds, before the demonstration

For the demonstration, the Pi connects directly to a display, so the audience can still see its output after all network links are disconnected. We first check that a complete body is visible and that classification windows are being produced. We then disconnect Wi-Fi and Ethernet and show that local processing and record creation continue. After reconnecting, we show pending records reach the cloud. If needed, we use a labeled public or synthetic video stored on the Pi. This website itself is only the presentation, not the live detection backend.

---

## Speaker notes · 35 seconds

To conclude, the project connects model research with a functioning edge–cloud prototype. MaskedBiMamba offers stronger precision and missing-frame tolerance, although the Transformer leads clean F1. The Pi can independently extract poses, classify motion and store records, and the cloud recovery tests preserve the event history. The remaining limits concern false alarms, transfer to new recording conditions and longer operation. We do not claim clinical readiness. The evidence appendix provides every exported aggregate value for questions and closer inspection.
