# Third-party provenance

## TCNTE

- Archive supplied by the user: `TCNTE-fall_detection-main.zip`
- Archive commit recorded in its ZIP comment/listing:
  `23b7d326cb9e39224bd36aa41b458227229a2663`
- Upstream: <https://github.com/SomeOtherScenery/fall_detection>
- Paper: *A Real-time skeleton-based fall detection algorithm based on temporal
  convolutional networks and transformer encoder* (2025).

The original scripts contain machine-specific Windows paths and select a model
after repeatedly evaluating the test loader. They are reference material and
are not imported by the new training pipeline. The new `tcnte` implementation
uses raw logits, an independent validation split, and a fully recorded config.

The paper reports TCN kernel size 5 while the released `network.py` constructs
the TCN with kernel size 3. Both choices are represented as explicit config
variants; the default reproduction config follows the paper table.

## Fall-Mamba

- Upstream: <https://github.com/DHUspeech/fall-mamba>
- Audited commit: `12885242b23a3b8fce59bfd652687beaca652d41`
- Paper: *Fall-Mamba: A Multimodal Fusion and Masked Mamba-Based Approach for
  Fall Detection* (IEEE IoT Journal, 2025).

The public repository currently provides core architecture fragments but not a
complete dataset, training and frame-masking pipeline. A future multimodal
adapter must pin the upstream commit and document every filled-in choice. The
skeleton MaskedBiMamba model in this repository is **inspired by**, not a claim
of exact reproduction of, Fall-Mamba.

