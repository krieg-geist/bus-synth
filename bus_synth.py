import asyncio
import hashlib
import multiprocessing
import time

import matplotlib
import websockets
import http.server
import socketserver
import json
import requests
from threading import Thread, Timer
from typing import Dict, Any
import matplotlib.pyplot as plt
from oscillator_manager import OscillatorManager
from dotenv import load_dotenv
import os

load_dotenv()

class BusSynth:
    def __init__(self):
        self.API_KEY = os.getenv('METLINK_API_KEY')
        self.BUS_URL = "https://api.opendata.metlink.org.nz/v1/gtfs-rt/vehiclepositions"
        self.STOP_URL = "https://api.opendata.metlink.org.nz/v1/gtfs/stops"
        self.UPDATES_URL = "https://api.opendata.metlink.org.nz/v1/gtfs-rt/tripupdates"
        self.UPDATE_LOOP = 10
        self.buses = {}
        self.stops = {}
        self.updates = {}
        self.route_color_map = {}

        self.bounds = [[None, None], [None, None]]

        self.get_stops(self.fetch_stop_data())

        self.osc = OscillatorManager(self.bounds, self.UPDATE_LOOP)

        initial_bus_data = self.fetch_bus_data()
        self.update_buses(initial_bus_data)
        
        initial_updates_data = self.fetch_updates_data()
        self.get_updates(initial_updates_data)

        print(f"Found {len(self.buses)} buses, {len(self.stops)} stops, {len(self.updates)} updates on startup.")


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
    
    def fetch_updates_data(self):
        headers = {
            "accept": "application/json",
            "x-api-key": self.API_KEY
        }
        response = requests.get(self.UPDATES_URL, headers=headers)
        if response.status_code == 200:
            return json.loads(response.content).get('entity')
        else:
            print(f"Failed to retrieve updates data: {response.status_code}")
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
    
    def get_updates(self, data):
        current_time = int(time.time())
        new_updates = 0
        
        for update in data:
            update_id = update['id']
            trip_update = update['trip_update']
            
            if 'stop_time_update' in trip_update:
                stop_time_update = trip_update['stop_time_update']
                
                timestamp = stop_time_update.get('arrival', {}).get('time', 0)
                stop_id = stop_time_update.get('stop_id')
                delay = max(10, abs(stop_time_update.get('arrival', {}).get('delay', 0)))
                
                if stop_id and delay and (timestamp > current_time):
                    # Only add updates that are in the future
                    if update_id not in self.updates:
                        new_updates += 1
                        print(f"New update added: ID {update_id}, Stop {stop_id}, Delay {delay}")
                    
                    self.updates[update_id] = {
                        'timestamp': timestamp,
                        'stop_id': stop_id,
                        'delay': delay
                    }
                    
                    # Calculate when to trigger the update
                    trigger_time = timestamp - current_time
                    
                    # Set a timer to call send_update
                    Timer(trigger_time, self.send_update, args=[update_id]).start()
        
        if new_updates > 0:
            print(f"Added {new_updates} new updates. Total updates: {len(self.updates)}")

    def send_update(self, update_id):
        if update_id in self.updates:
            update = self.updates[update_id]
            stop_id = update['stop_id']
            delay = update['delay']

            # Get the lat/lon of the corresponding stop
            if stop_id in self.stops:
                lat, lon = self.stops[stop_id]
                
                # Play noise with delay / 100 as the length
                noise_length = delay / 100
                self.osc.play_noise(lat, lon, noise_length)
            else:
                print(f'stop_id {stop_id} not found!')
            # Remove the update from the dictionary
            del self.updates[update_id]

    def hash_bus_id(self, bus_id):
        return int(hashlib.sha256(bus_id.encode()).hexdigest(), 16) % 10**8

    def update_buses(self, data):
        current_ids = set()
        new_buses = 0
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
                    new_buses += 1
                    print(f"New bus added: ID {bus_id}, Route {route_id}")
                self.osc.set_oscillator_bus(bus_id, self.buses[bus_id].lat_lon, self.buses[bus_id].bearing)

        for bus_id in list(self.buses.keys()):
            if bus_id not in current_ids:
                del self.buses[bus_id]
                self.osc.remove_oscillator(bus_id)

        self.update_route_color_map()

        if new_buses > 0:
            print(f"Added {new_buses} new buses. Total buses: {len(self.buses)}")

    def update_route_color_map(self):
        unique_routes = set(bus.route_id for bus in self.buses.values())
        if unique_routes != set(self.route_color_map.keys()):
            colormap = matplotlib.pyplot.get_cmap('tab20', len(unique_routes))
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
        colormap =  matplotlib.pyplot.get_cmap('tab20', len(self.stops))
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
            self.update_buses(self.fetch_bus_data())
            self.get_updates(self.fetch_updates_data())
            marker_data = self.generate_marker_data()
            await websocket.send(json.dumps({"type": "bus_update", "data": marker_data}))
            print('.')
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
    multiprocessing.freeze_support() # idk why this needs to be here but windows shits the bed without it
    bus_synth = BusSynth()
    bus_synth.main()
