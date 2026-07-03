# dora-openarm-dataset-replayer

A [dora-rs](https://dora-rs.ai) node that replays an existing OpenArm
Dataset.

The node loads one episode from an existing OpenArm Dataset and re-emits its
recorded actions, observations, and camera frames as dora outputs. Events are
replayed in their original order and at the same timing as the original
recording, so downstream nodes see the episode just as it happened.

## Install

```bash
pip install dora-openarm-dataset-replayer
```

## Examples

This node is meant to be used from a dora-rs dataflow. See the
[`example/`](example) directory for ready-to-use dataflows that replay
a dataset into MuJoCo and plot the camera streams.

Specify the dataset to replay by setting the `DATASET` environment
variable of the `replayer` node in the
[`dataflow.yaml`](example/dataflow.yaml) (use `EPISODE` to choose a
different episode), then run the
[`dataflow.yaml`](example/dataflow.yaml):

```bash
dora build example/dataflow.yaml
DATASET="..." dora run example/dataflow.yaml
```

[`dataflow-classifier.yaml`](example/dataflow-classifier.yaml) also
has a classifier node that reports whether the replayed task was
completed successfully from ceiling camera and arm observations in
real-time. Set its `QUESTION` environment variable to the question
used to make that judgment such as "Is there a green spoon inside the
blue case?".

```bash
dora build example/dataflow-classifier.yaml
DATASET="..." QUESTION="..." dora run example/dataflow-classifier.yaml
```

## Outputs

Only the outputs present in the dataset are emitted. Each output is sent at the
same relative time it was recorded.

| Output | Description |
| --- | --- |
| `arm_right_action` | Target joint positions (`qpos`) for the right arm |
| `arm_left_action` | Target joint positions (`qpos`) for the left arm |
| `arm_right_observation` | Observed `qpos`, `qvel` and `qtorque` when recorded, for the right arm |
| `arm_left_observation` | Observed `qpos`, `qvel` and `qtorque` when recorded, for the left arm |
| `lifter_action` | Lifter elevation action |
| `lifter_observation` | Lifter elevation observation |
| `camera_wrist_right` | JPEG-encoded right wrist camera frames, with `encoding`, `width` and `height` metadata |
| `camera_wrist_left` | JPEG-encoded left wrist camera frames, with `encoding`, `width` and `height` metadata |
| `camera_ceiling` | JPEG-encoded ceiling camera frames, with `encoding`, `width` and `height` metadata |
| `camera_head_right` | JPEG-encoded right head camera frames, with `encoding`, `width` and `height` metadata |
| `camera_head_left` | JPEG-encoded left head camera frames, with `encoding`, `width` and `height` metadata |

## Command line options

Each option can also be set through the corresponding environment variable.

| Option | Environment variable | Default | Description |
| --- | --- | --- | --- |
| `--dataset` | `DATASET` | (required) | Path to the OpenArm Dataset |
| `--episode` | `EPISODE` | `0` | Index of the episode to replay |

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

Copyright 2026 Enactic, Inc.

## Code of Conduct

All participation in the OpenArm project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
