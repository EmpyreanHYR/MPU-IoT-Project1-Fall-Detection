# FallGuard speaker manuscript

Twelve slides, approximately seven minutes of prepared speech, leaving room for transitions within the 7–8 minute slot. The demonstration is separate. Speaking roles should be assigned by the team.

## 01 · Opening (25 seconds)

Our project is FallGuard, a camera-based fall-detection prototype. MaskedBiMamba classifies one-second pose sequences, while a Raspberry Pi extracts poses, runs the classifier, and stores records locally. Hailo accelerates pose extraction. Detection continues without Internet access, and the cloud receives retained records after reconnection. We will explain the model, the evidence, and the complete data flow.

## 02 · Care setting (30 seconds)

A fall can resemble sitting or bending in one frame. Motion provides context, but estimated poses can be interrupted. Our model addresses incomplete observations within a short sequence. The intended care setting also requires an event history that remains available after a network interruption. Our contribution combines temporal modeling and pose quality with local execution and deferred cloud delivery.

## 03 · System (35 seconds)

Follow the four local stages: camera or video, pose extraction, temporal classification, and SQLite storage. Hailo runs the pose network; the Pi CPU runs MaskedBiMamba. A local page displays predictions and pending records without a cloud connection. The cloud stores records before acknowledging them. Retries retain the original capture time and do not duplicate the tested records. Compared with the proposal, classification has moved from the cloud to the device.

## 04 · Model (45 seconds)

The input contains twelve body joints, with normalized coordinates and confidence. Training masks selected frames. Temporal attention connects positions, and independent forward and backward Mamba branches process the buffered window. A learned quality gate weights frame features using mean joint confidence, visible-joint fraction, and person confidence. Both directions use observations already collected within one second. We reuse the Mamba operator; our work is the combined architecture, evaluation, and system integration.

## 05 · Evaluation (35 seconds)

The primary study combines CAUCAFall and GMDCSA-24: 260 videos and fourteen subject groups. Four subject-disjoint folds and three seeds give twelve evaluations per model. Le2i has a separate baseline study and external evaluation. Forty synthetic clips test edge deployment. Window, video, event, and confirmed-alert metrics answer different questions. Error bars are sample standard deviations. Evaluated video-hour rates must not be interpreted as a full day of continuous monitoring.

## 06 · Baselines (40 seconds)

The Transformer encoder leads clean window F1 at 0.6581. MaskedBiMamba leads window precision at 0.6048, with video F1 of 0.7632. Its unmatched predicted-event rate is lowest at the common threshold. Confirmation rules are evaluated separately: replay gives confirmed-event recall of 0.7752 and 66.7 unmatched confirmed alerts per evaluated hour. This illustrates the sensitivity-precision trade-off. These short test segments do not establish an acceptable continuous-care notification rate.

## 07 · Ablations (35 seconds)

We compare ten variants under the same folds and seeds. Removing the backward branch or temporal attention reduces window F1 and increases unmatched predicted events. Other changes have mixed effects. Removing masking improves clean window F1, and removing quality pooling improves clean video F1. The evidence supports the temporal components, while masking and quality processing require calibration for the intended observation conditions. Clean ablations do not isolate the cause of frame-loss tolerance.

## 08 · Robustness (35 seconds)

At thirty percent frame removal, MaskedBiMamba retains window F1 of 0.6276, compared with 0.4361 for TCNTE. A similar trend appears on external Le2i. The current comparison includes frame removal and confidence noise. Earlier joint-removal tests also changed coordinate normalization, so they have been excluded from the model conclusions. They remain clearly marked in the historical archive. These pose perturbations do not evaluate changes in lighting or camera position.

## 09 · Edge deployment (45 seconds)

The full Pi pipeline was tested without external network access. Using the same YOLOv8s-pose model, throughput is 20.56 fps with Hailo and 1.73 fps with CPU ONNX, an 11.9-fold difference. Classification still runs on the Pi CPU. Of forty synthetic clips, thirty-nine produce outputs: twenty true positives, eleven true negatives, eight false positives, and one missing output. Only fourteen positive clips are detected within the annotated fall interval, distinguishing clip recall from timely event detection.

## 10 · Cloud recovery (40 seconds)

A thirty-second upload-path outage retains seventeen records on the Pi. The queue is first observed empty 2.83 seconds after recovery. All eighty-five tested records match their identifiers and capture times. Replaying thirty-four records after a cloud restart creates no duplicates. Separately, one hundred committed writes survive forced writer termination. A ten-minute offline replay processes 11,016 frames without reported throttling. Receipt latency starts at the final captured frame, not at fall onset.

## 11 · Demonstration (25 seconds)

For the demonstration, connect the Pi directly to a display. Show valid poses and increasing classification counts, disconnect Wi-Fi and Ethernet, then show local records accumulating. Reconnect and show the same records in the cloud. A labeled public or synthetic video is the backup input. This presentation displays evidence; the local dashboard and real cloud backend provide the operational demonstration.

## 12 · Conclusions (30 seconds)

The project combines temporal modeling, independent edge inference, and persistent cloud delivery. MaskedBiMamba offers higher precision at the common threshold and stronger frame-loss tolerance than TCNTE; TE leads clean F1. The main remaining tasks are alert calibration on continuous recordings and longer camera tests. Our repository provides experiment code, manuscripts, and aggregate evidence. The appendix separates current evidence from excluded historical conditions. Thank you.

## A · Evidence appendix

The archive retains 1,853 aggregate rows, with excluded spatial-mask conditions labeled and accessible separately. Confirmed-alert replay is a distinct 12-run analysis. Counts are aggregate rows, not video or participant counts. Use the eligible/current views for conclusions; do not cite excluded spatial-mask rows as missing-joint evidence.
