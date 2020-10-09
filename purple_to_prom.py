#!/usr/bin/env python3

# MIT License
# Copyright (c) 2020 Will Bertelsen
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
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
import traceback
from typing import List


import aqi
import json
import requests
import argparse
import prometheus_client


aqi_g = prometheus_client.Gauge(
    'purpleair_pm_25_10m_iaqi', 'iAQI (10 min average)',
    ['parent_sensor_id', 'sensor_id', 'sensor_name']
)
aqi_AQandU_g = prometheus_client.Gauge(
    'purpleair_pm_25_10m_iaqi_AQandU', 'iAQI (10 min average) w/ AQandU correction',
    ['parent_sensor_id', 'sensor_id', 'sensor_name']
)
aqi_LRAPA_g = prometheus_client.Gauge(
    'purpleair_pm_25_10m_iaqi_LRAPA', 'iAQI (10 min average) w/ LRAPA correction',
    ['parent_sensor_id', 'sensor_id', 'sensor_name']
)
temp_g = prometheus_client.Gauge(
    'purpleair_temp_f', 'Sensor temp reading (degrees Fahrenheit)',
    ['parent_sensor_id', 'sensor_id', 'sensor_name']
)
humidity_g = prometheus_client.Gauge(
    'purpleair_humidity_pct', 'Sensor humidity reading (percent)',
    ['parent_sensor_id', 'sensor_id', 'sensor_name']
)
pressure_g = prometheus_client.Gauge(
    'purpleair_pressure_mb', 'Sensor pressure reading (millibars)',
    ['parent_sensor_id', 'sensor_id', 'sensor_name']
)


def check_sensor(parent_sensor_id: str) -> None:
    resp = requests.get("https://www.purpleair.com/json?show={}".format(parent_sensor_id))
    if resp.status_code != 200:
        raise Exception("got {} responde code from purpleair".format(resp.status_code))

    try:
        resp_json = resp.json()
    except ValueError:
        return
    for sensor in resp_json.get("results"):
        sensor_id = sensor.get("ID")
        name = sensor.get("Label")
        stats = sensor.get("Stats")
        temp_f = sensor.get("temp_f")
        humidity = sensor.get("humidity")
        pressure = sensor.get("pressure")
        if stats:
            stats = json.loads(stats)
            pm25_10min = stats.get("v1")
            if pm25_10min:
                i_aqi = aqi.to_iaqi(aqi.POLLUTANT_PM25, pm25_10min, algo=aqi.ALGO_EPA)
                aqi_g.labels(
                    parent_sensor_id=parent_sensor_id, sensor_id=sensor_id, sensor_name=name
                ).set(i_aqi)

                # https://www.aqandu.org/airu_sensor#calibrationSection
                pm25_10min_AQandU = 0.778 * float(pm25_10min) + 2.65
                i_aqi_AQandU = aqi.to_iaqi(aqi.POLLUTANT_PM25, pm25_10min_AQandU, algo=aqi.ALGO_EPA)
                aqi_AQandU_g.labels(
                    parent_sensor_id=parent_sensor_id, sensor_id=sensor_id, sensor_name=name
                ).set(i_aqi_AQandU)

                # https://www.lrapa.org/DocumentCenter/View/4147/PurpleAir-Correction-Summary
                pm25_10min_LRAPA = 0.5 * float(pm25_10min) - 0.66
                i_aqi_LRAPA = aqi.to_iaqi(aqi.POLLUTANT_PM25, pm25_10min_LRAPA, algo=aqi.ALGO_EPA)
                aqi_LRAPA_g.labels(
                    parent_sensor_id=parent_sensor_id, sensor_id=sensor_id, sensor_name=name
                ).set(i_aqi_LRAPA)

        if temp_f:
            temp_g.labels(
                parent_sensor_id=parent_sensor_id, sensor_id=sensor_id, sensor_name=name
            ).set(float(temp_f))
        if pressure:
            pressure_g.labels(
                parent_sensor_id=parent_sensor_id, sensor_id=sensor_id, sensor_name=name
            ).set(float(pressure))
        if humidity:
            humidity_g.labels(
                parent_sensor_id=parent_sensor_id, sensor_id=sensor_id, sensor_name=name
            ).set(float(humidity))


def poll(sensor_ids: List[str], refresh_seconds: int) -> None:
    while True:
        print("refreshing sensors...", flush=True)
        for sensor_id in sensor_ids:
            try:
                check_sensor(sensor_id)
            except Exception as e:
                traceback.print_exc()
                print("Error fetching sensor data, sleeping till next poll")
                break
        time.sleep(refresh_seconds)


def main():
    parser = argparse.ArgumentParser(
        description="Gets sensor data from purple air, converts it to AQI, and exports it to prometheus"
    )
    parser.add_argument('--sensor-ids', nargs="+", help="Sensors to collect from", required=True)
    parser.add_argument("--port", type=int, help="What port to serve prometheus metrics on", default=9760)
    parser.add_argument("--refresh-seconds", type=int, help="How often to refresh", default=60)
    args = parser.parse_args()

    prometheus_client.start_http_server(args.port)

    print("Serving prometheus metrics on {}/metrics".format(args.port))
    poll(args.sensor_ids, args.refresh_seconds)


if __name__ == "__main__":
    main()
