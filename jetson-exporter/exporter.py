#!/usr/bin/python3
# -*- coding: utf-8 -*-

# MIT License
#
# Copyright (c) 2021 Stefan von Cavallar
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
import atexit
import argparse
from jtop import jtop
from prometheus_client.core import InfoMetricFamily, GaugeMetricFamily, REGISTRY
from prometheus_client import start_http_server


class CustomCollector(object):
    def __init__(self):
        atexit.register(self.cleanup)
        self._jetson = jtop()
        self._jetson.start()

    def cleanup(self):
        print("Closing jetson-stats connection...")
        self._jetson.close()

    def collect(self):
        if self._jetson.ok():
            # print('emc: ', self._jetson.emc)
            # print('iram: ', self._jetson.iram)
            # print('mts: ', self._jetson.mts)

            #
            # Board info
            #
            i = InfoMetricFamily(
                "jetson_info_board", "Board platform info", labels=["board_info"]
            )
            i.add_metric(
                ["platform"],
                {
                    "Machine": self._jetson.board["platform"]["Machine"],
                    "System": self._jetson.board["platform"]["System"],
                    "Distribution": self._jetson.board["platform"]["Distribution"],
                    "Release": self._jetson.board["platform"]["Release"],
                    "Python": self._jetson.board["platform"]["Python"],
                },
            )
            yield i

            i = InfoMetricFamily(
                "jetson_info_hardware", "Board hardware info", labels=["board_hw"]
            )
            i.add_metric(
                ["hardware"],
                {
                    "Model": self._jetson.board["hardware"]["Model"],
                    "Module": self._jetson.board["hardware"]["Module"],
                    "SoC": self._jetson.board["hardware"]["SoC"],
                    "CUDA Arch BIN": self._jetson.board["hardware"]["CUDA Arch BIN"],
                    "L4T": self._jetson.board["hardware"]["L4T"],
                    "Jetpack": self._jetson.board["hardware"]["Jetpack"],
                },
            )
            yield i

            #
            # NV power mode
            #
            i = InfoMetricFamily("jetson_nvpmode", "NV power mode", labels=["nvpmode"])
            i.add_metric(["mode"], {"mode": self._jetson.nvpmodel.name})
            yield i

            #
            # System uptime
            #
            g = GaugeMetricFamily("jetson_uptime", "System uptime", labels=["uptime"])
            days = self._jetson.uptime.days
            seconds = self._jetson.uptime.seconds
            hours = seconds // 3600
            minutes = (seconds // 60) % 60
            g.add_metric(["days"], days)
            g.add_metric(["hours"], hours)
            g.add_metric(["minutes"], minutes)
            yield g

            #
            # CPU usage
            #
            g = GaugeMetricFamily("jetson_usage_cpu", "CPU % schedutil", labels=["cpu"])
            for idx, cpu in enumerate(self._jetson.cpu["cpu"]):
                g.add_metric([f"cpu_{idx}"], cpu["system"])
            yield g

            #
            # GPU usage
            #
            g = GaugeMetricFamily("jetson_usage_gpu", "GPU % schedutil", labels=["gpu"])
            g.add_metric(["val"], self._jetson.gpu["gpu"]["status"]["load"])
            yield g

            #
            # RAM usage
            #
            g = GaugeMetricFamily("jetson_usage_ram", "Memory usage", labels=["memory"])
            g.add_metric(["used"], self._jetson.memory["RAM"]["used"])
            g.add_metric(["shared"], self._jetson.memory["RAM"]["shared"])
            yield g

            #
            # Disk usage
            #
            g = GaugeMetricFamily(
                "jetson_usage_disk", "Disk space usage", labels=["disk"]
            )
            g.add_metric(["used"], self._jetson.disk["used"])
            g.add_metric(["total"], self._jetson.disk["total"])
            g.add_metric(["available"], self._jetson.disk["available"])
            g.add_metric(["available_no_root"], self._jetson.disk["available_no_root"])
            yield g

            #
            # Fan usage
            #
            g = GaugeMetricFamily("jetson_usage_fan", "Fan usage", labels=["fan"])
            g.add_metric(["speed"], self._jetson.fan["pwmfan"]["speed"])
            g.add_metric(["profile"], self._jetson.fan["pwmfan"]["profile"])
            yield g

            #
            # Swapfile usage
            #
            g = GaugeMetricFamily(
                "jetson_usage_swap", "Swapfile usage", labels=["swap"]
            )
            g.add_metric(["used"], self._jetson.memory["SWAP"]["used"])
            g.add_metric(["total"], self._jetson.memory["SWAP"]["tot"])
            yield g

            #
            # Sensor temperatures
            #
            g = GaugeMetricFamily(
                "jetson_temperatures", "Sensor temperatures", labels=["temperature"]
            )
            devices = ["cpu", "cv0", "cv1", "cv2", "gpu", "soc0", "soc1", "soc2", "tj"]
            for device in devices:
                g.add_metric(
                    [f"{device}"],
                    (
                        self._jetson.temperature[f"{device}"]
                        if device in self._jetson.temperature
                        else 0
                    ),
                )
            yield g

            #
            # Power
            #
            g = GaugeMetricFamily("jetson_usage_power", "Power usage", labels=["power"])
            g.add_metric(["total_curr"], self._jetson.power["tot"]["curr"])
            g.add_metric(
                ["VDD_CPU_GPU_CV_curr"],
                self._jetson.power["rail"]["VDD_CPU_GPU_CV"]["curr"],
            )
            g.add_metric(
                ["VDD_SOC_curr"], self._jetson.power["rail"]["VDD_SOC"]["curr"]
            )
            yield g


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, default=8000, help="Metrics collector port number"
    )

    args = parser.parse_args()

    start_http_server(args.port)
    REGISTRY.register(CustomCollector())
    while True:
        time.sleep(1)
