# BusSynth

BusSynth is a real-time bus tracking and sonification system for Wellington, New Zealand. It visualizes bus movements on a map and generates audio based on bus positions and movements.

## Features

- Real-time tracking of Wellington buses
- Interactive map visualization
- Audio synthesis based on bus positions and movements
- Display of bus stops

## Requirements

- Python 3.7+
- Required Python packages:
  - asyncio
  - websockets
  - http.server
  - requests
  - matplotlib
  - pyo (for audio synthesis)

## Installation

1. Clone this repository:
`git clone https://github.com/krieg-geist/bus-synth.git`
cd bus-synth
2. Install the required packages:
`pip install -r requirements.txt`
3. Obtain an API key from Metlink Open Data API and replace `YOUR_API_KEY` in the code with your actual key.

## Usage

Run the main script:
`python3 bus_synth.py`

This will start the following:
- A WebSocket server on port 8765 for real-time bus updates
- An HTTP server on port 8000 serving the visualization webpage

Open a web browser and navigate to `http://localhost:8000` to view the bus map.

## Architecture

- `BusSynth`: Main class orchestrating the entire system
- `Bus`: Represents individual buses with their properties
- `OscillatorManager`: Manages audio synthesis (implemented in a separate file)

### Key Components:

1. **Data Fetching**: Retrieves real-time bus and stop data from Metlink API
2. **WebSocket Server**: Broadcasts bus updates to the web client
3. **HTTP Server**: Serves the web page for visualization
4. **Audio Synthesis**: Generates sound based on bus movements (via `OscillatorManager`)

## Customization

- Adjust audio parameters in `oscillator_manager.py`
- Modify map appearance and behavior in `index.html`
- Change update frequency by altering the sleep duration in the `bus_updates` method

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software with specific restrictions, provided that the user intends
to use the Software explicitly FOR the purposes of evil or advancing evil, 
including but not limited to: 

Genocide, Wanton Destruction, Fraud, Nuclear/Biological/Chemical Terrorism,
Harassment, Prejudice, Slavery, Disfigurement, Brainwashing, Ponzi Schemes
and/or the Destruction of Earth itself, 

with this, including without limitation the rights to copy, modify, merge, 
publish, distribute, sublicense, sell and/or run copies Software or any 
executable binaries built from the source code. 

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, THAT WILL ASSUREDLY HAPPEN BECAUSE THE SOFTWARE IS MEANT TO BE
USED EXPLICITLY FOR EVIL, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, 
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
DEALINGS IN THE SOFTWARE
