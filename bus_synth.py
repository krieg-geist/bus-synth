import asyncio
import hashlib
import multiprocessing

import matplotlib
import websockets
import http.server
import socketserver
import json
import requests
from threading import Thread
from typing import Dict, Any
import matplotlib.pyplot as plt
from oscillator_manager import OscillatorManager


class BusSynth:
    def __init__(self):
        self.API_KEY = "I7Ozj1IWrV2b2owUdGqJi1CVJ4FFi5xm9fKdj5UB"
        self.BUS_URL = "https://api.opendata.metlink.org.nz/v1/gtfs-rt/vehiclepositions"
        self.STOP_URL = "https://api.opendata.metlink.org.nz/v1/gtfs/stops"
        self.UPDATE_LOOP = 10
        self.buses = {}
        self.stops = {}
        self.route_color_map = {}

        self.bounds = [[None, None], [None, None]]
        self.get_stops(self.fetch_stop_data())

        self.osc = OscillatorManager(self.bounds, self.UPDATE_LOOP)

    def fetch_bus_data(self):
        headers = {
            "accept": "application/json",
            "x-api-key": self.API_KEY
        }
        response = requests.get(self.BUS_URL, headers=headers)
        if response.status_code == 200:
            return json.loads(response.content).get('entity')
        else:
            print(f"Failed to retrieve bus data: {response.status_code}")
            return []

    def fetch_stop_data(self):
        headers = {
            "accept": "application/json",
            "x-api-key": self.API_KEY
        }
        response = requests.get(self.STOP_URL, headers=headers)
        if response.status_code == 200:
            return json.loads(response.content)
        else:
            print(f"Failed to retrieve stop data: {response.status_code}")
            return []

    def get_stops(self, data):
        for stop in data:
            stop_id = stop['stop_id']
            stop_lat = stop['stop_lat']
            stop_lon = stop['stop_lon']
            self.stops[stop_id] = (stop_lat, stop_lon)

            # Update bounds
            if self.bounds[0][0] is None or stop_lat < self.bounds[0][0]:
                self.bounds[0][0] = stop_lat
            if self.bounds[0][1] is None or stop_lat > self.bounds[0][1]:
                self.bounds[0][1] = stop_lat
            if self.bounds[1][0] is None or stop_lon < self.bounds[1][0]:
                self.bounds[1][0] = stop_lon
            if self.bounds[1][1] is None or stop_lon > self.bounds[1][1]:
                self.bounds[1][1] = stop_lon

    def hash_bus_id(self, bus_id):
        return int(hashlib.sha256(bus_id.encode()).hexdigest(), 16) % 10**8

    def update_buses(self, data):
        current_ids = set()
        for entity in data:
            vehicle_info = entity.get('vehicle')
            if vehicle_info:
                bus_id = vehicle_info['vehicle']['id']
                try:
                    bus_id = int(bus_id)
                except ValueError:
                    bus_id = self.hash_bus_id(bus_id)
                current_ids.add(bus_id)
                route_id = vehicle_info['trip']['route_id']
                position = vehicle_info['position']

                if bus_id in self.buses:
                    self.buses[bus_id].update_position(position)
                else:
                    self.buses[bus_id] = Bus(bus_id, route_id, position)
                    self.osc.add_oscillator(bus_id)
                self.osc.set_oscillator_bus(bus_id, self.buses[bus_id].lat_lon, self.buses[bus_id].bearing)


        for bus_id in list(self.buses.keys()):
            if bus_id not in current_ids:
                del self.buses[bus_id]
                self.osc.remove_oscillator(bus_id)

        self.update_route_color_map()

    def update_route_color_map(self):
        unique_routes = set(bus.route_id for bus in self.buses.values())
        if unique_routes != set(self.route_color_map.keys()):
            colormap = plt.cm.get_cmap('tab20', len(unique_routes))
            colors = [colormap(i) for i in range(len(unique_routes))]
            self.route_color_map = {route: colors[i] for i, route in enumerate(unique_routes)}

    def generate_marker_data(self):
        marker_data = []
        for id, bus in self.buses.items():
            color = self.route_color_map[bus.route_id]
            marker_data.append({
                'id': str(id),
                'lat': bus.lat_lon[0],
                'lon': bus.lat_lon[1],
                'bearing': bus.bearing,
                'color': matplotlib.colors.rgb2hex(color),
                'tooltip': f"Route: {bus.route_id}<br>Bus ID: {bus.id}"
            })
        return json.dumps(marker_data)

    def generate_stop_marker_data(self):
        marker_data = []
        colormap = plt.cm.get_cmap('tab20', len(self.stops))
        for idx, (id, latlon) in enumerate(self.stops.items()):
            color = colormap(idx)
            marker_data.append({
                'id': id,
                'lat': latlon[0],
                'lon': latlon[1],
                'color': matplotlib.colors.rgb2hex(color),
                'tooltip': f"Stop: {id}<br>"
            })
        return json.dumps(marker_data)

    async def bus_updates(self, websocket, path):
        stop_markers = self.generate_stop_marker_data()
        await websocket.send(json.dumps({"type": "stop_update", "data": stop_markers}))
        while True:
            data = self.fetch_bus_data()
            self.update_buses(data)
            marker_data = self.generate_marker_data()
            await websocket.send(json.dumps({"type": "bus_update", "data": marker_data}))
            await asyncio.sleep(self.UPDATE_LOOP)

    def run_websocket_server(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        start_server = websockets.serve(self.bus_updates, "localhost", 8765)
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

    def main(self):
        Thread(target=self.run_websocket_server, daemon=True).start()

        class RequestHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    with open('index.html', 'rb') as file:
                        self.wfile.write(file.read())
                else:
                    super().do_GET()

        with socketserver.TCPServer(("", 8000), RequestHandler) as httpd:
            print("Serving at port 8000")
            httpd.serve_forever()

class Bus:
    def __init__(self, id: str, route_id: int, position: Dict[str, Any]):
        self.id = id
        self.route_id = route_id
        self.lat_lon = (position.get('latitude'), position.get('longitude'))
        self.update_position(position)

    def update_position(self, new_position: Dict[str, Any]):
        self.lat_lon = (new_position.get('latitude'), new_position.get('longitude'))
        self.bearing = new_position.get('bearing')

    def __repr__(self):
        return f"Bus(id={self.id}, route_id={self.route_id}, position={self.lat_lon})"

if __name__ == '__main__':
    multiprocessing.freeze_support()
    bus_synth = BusSynth()
    bus_synth.main()