# Copyright 2026 Enactic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""dora-rs node that replays OpenArm Dataset in dora-rs dataflow."""

import argparse
import dora
import openarm_dataset
import os
import pandas as pd
import pathlib
import pyarrow as pa
import tempfile
import time


class Replayer:
    """Replays an episode in a dataset."""

    def __init__(self, dataset, episode_index):
        """Initialize."""
        self._dataset = dataset
        self._episode = self._dataset.meta.episodes[episode_index]
        actions = self._dataset.load_action(self._episode)
        observations = self._dataset.load_obs(self._episode)
        cameras = self._dataset.load_cameras(self._episode)

        def build_arm_action_iterator(side):
            qpos = observations[f"arms/{side}/qpos"]
            df = pd.DataFrame(index=qpos.index)
            df["qpos"] = qpos.to_numpy().tolist()
            return df.itertuples()

        def build_arm_observation_iterator(side):
            qpos = observations[f"arms/{side}/qpos"]
            df = pd.DataFrame(index=qpos.index)
            df["qpos"] = qpos.to_numpy().tolist()
            for name in ["qvel", "qtorque"]:
                key = f"arms/{side}/{name}"
                if key in observations:
                    df[name] = observations[key].to_numpy().tolist()
            return df.itertuples()

        self._iterators = {
            "arm_right_action": build_arm_action_iterator("right"),
            "arm_left_action": build_arm_action_iterator("left"),
            "arm_right_observation": build_arm_observation_iterator("right"),
            "arm_left_observation": build_arm_observation_iterator("left"),
        }
        if "lifter/elevation" in actions:
            self._iterators["lifter_action"] = actions["lifter/elevation"].itertuples()
        if "lifter/elevation" in observations:
            self._iterators["lifter_observation"] = observations[
                "lifter/elevation"
            ].itertuples()
        for key, camera in cameras.items():
            self._iterators[f"camera_{key}"] = camera.frames()

    def __iter__(self):
        """Yield events at the same timing as the original."""
        next_values = {}

        def get_timestamp(value):
            if isinstance(value, openarm_dataset.camera.Frame):
                return value.timestamp
            else:
                # pandas' timestamp
                return value[0].value / 1_000_000_000.0

        def sort_key(kv):
            return get_timestamp(kv[1])

        def build_data(value):
            if isinstance(value, openarm_dataset.camera.Frame):
                with tempfile.TemporaryDirectory() as temp_dir:
                    path = value.materialize(temp_dir)
                    image = value.open_image()
                    with open(path, "rb") as input:
                        return (
                            pa.array(input.read(), type=pa.uint8()),
                            {
                                "encoding": "jpeg",
                                "width": image.size[0],
                                "height": image.size[1],
                            },
                        )
            else:

                def build_array(v):
                    if isinstance(v, list):
                        return pa.array([v], type=pa.list_(pa.float32()))
                    else:
                        return pa.array([v], type=pa.float32())

                if len(value._fields) == 2:  # index and one field
                    if isinstance(value[1], list):
                        return pa.array(value[1], type=pa.float32()), {}
                    else:
                        return pa.array([value[1]], type=pa.float32()), {}
                else:
                    arrays = [build_array(v) for v in value[1:]]
                    return (
                        pa.StructArray.from_arrays(arrays, names=value._fields[1:]),
                        {},
                    )

        base_timestamp = None
        while True:
            if len(self._iterators) == 0:
                break
            deleted_names = []
            for name, iterator in self._iterators.items():
                if name not in next_values:
                    try:
                        next_values[name] = next(iterator)
                    except StopIteration:
                        deleted_names.append(name)
            for name in deleted_names:
                del self._iterators[name]
            if not next_values:
                break
            name, next_value = sorted(next_values.items(), key=sort_key)[0]
            del next_values[name]
            timestamp = get_timestamp(next_value)
            if base_timestamp is None:
                base_timestamp = timestamp
            elapsed_time = timestamp - base_timestamp
            data, metadata = build_data(next_value)
            yield name, elapsed_time, data, metadata


def main():
    """Replay an existing OpenArm Dataset in a dora-rs dataflow."""
    parser = argparse.ArgumentParser(description="Replay an OpenArm Dataset")
    parser.add_argument(
        "--dataset",
        type=pathlib.Path,
        default=os.getenv("DATASET"),
        help="Path to the OpenArm Dataset",
    )
    parser.add_argument(
        "--episode",
        type=int,
        default=int(os.getenv("EPISODE", 0)),
        help="The Nth episode to replay",
    )
    args = parser.parse_args()

    node = dora.Node()
    dataset = openarm_dataset.Dataset(args.dataset)
    replayer = Replayer(dataset, args.episode)
    base_time = None
    for name, elapsed_time, data, metadata in replayer:
        if base_time is None:
            base_time = time.time()
        else:
            emit_time = base_time + elapsed_time
            while True:
                timeout = emit_time - time.time()
                if timeout <= 0:
                    break
                event = node.next(timeout)
                if not event:
                    break
                if event["type"] == "STOP":
                    return
            timeout = emit_time - time.time()
            if timeout > 0:
                time.sleep(timeout)
        node.send_output(name, data, metadata)


if __name__ == "__main__":
    main()
