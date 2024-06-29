from asyncio import sleep
import time
import multiprocessing
import numpy as np
from pyo import *

class Oscillator:
    def __init__(self, freq=440, feedback=0.1, mul=0.005, pan=0.5, loop_rate=10):
        self.freq = SigTo(freq, time=loop_rate)
        self.feedback = SigTo(feedback, time=loop_rate)
        self.mul = SigTo(mul, time=loop_rate)
        self.pan_value = SigTo(pan, time=loop_rate)

        self.loop_rate = loop_rate
        
        self.osc = SineLoop(freq=self.freq, feedback=self.feedback, mul=self.mul)
        self.pan = Pan(self.osc, outs=2, pan=self.pan_value).out()

    def set(self, freq=None, amp=None, pan=None, feedback=None):
        if freq is not None:
            self.freq.time = self.loop_rate
            self.freq.value = freq
        if amp is not None:
            self.mul.time = self.loop_rate
            self.mul.value = amp
        if pan is not None:
            self.pan_value.time = self.loop_rate
            self.pan_value.value = pan
        if feedback is not None:
            self.feedback.time = self.loop_rate
            self.feedback.value = feedback

    def stop(self):
        self.osc.stop()

class Group(multiprocessing.Process):
    def __init__(self):
        super(Group, self).__init__()
        self.daemon = True
        self._terminated = False
        self.oscillators = {}
        self.command_queue = multiprocessing.Queue()

    def run(self):
        self.server = Server()
        self.server.deactivateMidi()
        self.server.boot().start()

        while not self._terminated:
            try:
                command, args = self.command_queue.get(timeout=0.1)
                if command == 'add':
                    osc_id, freq, feedback = args
                    self.oscillators[osc_id] = Oscillator(freq=freq, feedback=feedback)
                elif command == 'remove':
                    osc_id = args
                    if osc_id in self.oscillators:
                        self.oscillators[osc_id].stop()
                        del self.oscillators[osc_id]
                elif command in ['set_pitch', 'set_amplitude', 'set_pan', 'set_feedback']:
                    osc_id, value = args
                    if osc_id in self.oscillators:
                        param = {'set_pitch': 'freq', 'set_amplitude': 'amp', 'set_pan': 'pan', 'set_feedback': 'feedback'}[command]
                        self.oscillators[osc_id].set(**{param: value})
                elif command == 'play_noise':
                    pan, cutoff, length = args
                    self.play_noise(pan, cutoff, length)
        
            except multiprocessing.queues.Empty:
                time.sleep(0.001)

        for osc in self.oscillators.values():
            osc.stop()
        self.server.stop()

    def command(self, command, args):
        self.command_queue.put((command, args))

    def stop(self):
        self._terminated = True

    def play_noise(self, pan, cutoff, length):
        env = Adsr(dur=length)
        noise = Noise(mul=0.7)
        filter = Biquad(noise, freq=cutoff, q=1, type=0)
        out = Pan(filter, outs=2, pan=pan)
        out = out * env  # Apply envelope to the filtered and panned noise
        out.out()
        env.play()
        time.sleep(length + 0.1)  # Wait for the sound to finish

class OscillatorManager:
    def __init__(self, range=[[-41.4, 174.6], [-41.2, 174.9]], update_loop=10):
        multiprocessing.freeze_support()
        self.group = Group()
        self.group.start()
        self.lat_range = (range[0][0], range[0][1])
        self.lon_range = (range[1][0], range[1][1])
        self.freq_range = (50, 10000)

    def add_oscillator(self, osc_id, freq=440, feedback=0.1):
        self.group.command('add', (osc_id, freq, feedback))

    def remove_oscillator(self, osc_id):
        self.group.command('remove', osc_id)

    def set_oscillator_pitch(self, osc_id, freq):
        self.group.command('set_pitch', (osc_id, freq))

    def set_oscillator_feedback(self, osc_id, feedback):
        self.group.command('set_feedback', (osc_id, feedback))

    def set_oscillator_amplitude(self, osc_id, amp):
        self.group.command('set_amplitude', (osc_id, amp))

    def set_oscillator_pan(self, osc_id, pan):
        self.group.command('set_pan', (osc_id, pan))

    def set_oscillator_bus(self, osc_id, coords, bearing):
        lat, lon = coords
        lat = min(max(lat, self.lat_range[0]), self.lat_range[1])
        lon = min(max(lon, self.lon_range[0]), self.lon_range[1])
        freq = int(np.interp(lon, self.lon_range, self.freq_range))
        feedback = float(np.interp(lat, self.lat_range, (0, 1)))
        self.set_oscillator_pitch(osc_id, freq)
        self.set_oscillator_pan(osc_id, 1 / 360 * bearing)
        self.set_oscillator_feedback(osc_id, feedback)
    
    def play_noise(self, lat, lon, length):
        lat = min(max(lat, self.lat_range[0]), self.lat_range[1])
        lon = min(max(lon, self.lon_range[0]), self.lon_range[1])
        
        pan = float(np.interp(lon, self.lon_range, (0, 1)))
        cutoff = int(np.interp(lat, self.lat_range, (200, 15000)))
        
        self.group.command('play_noise', (pan, cutoff, length))

    def quit(self):
        self.group.stop()
        self.group.join()

if __name__ == '__main__':
    manager = OscillatorManager()

    # Example usage:
    manager.add_oscillator(1, 440, 0.1)
    manager.add_oscillator(2, 550, 0.1)
    manager.set_oscillator_pitch(1, 660)
    manager.set_oscillator_amplitude(2, 0.01)
    manager.set_oscillator_pan(2, 0.1)
    manager.set_oscillator_feedback(1, 0.5)
    manager.set_oscillator_bus(2, (-41.39, 174.70), 90)
    manager.remove_oscillator(1)