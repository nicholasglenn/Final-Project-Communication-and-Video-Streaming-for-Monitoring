import io
import logging
import socketserver
import json
import time
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform

from robot_control import pause_movement, continue_movement, turn_servo  # Import fungsi kontrol dari robot_control

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Control Panel</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f4f4f4;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
 
  .header {
    width: 100%;
    background-color: #004225; /* Darker green for contrast */
    color: white;
    padding: 0.5rem 0;
    text-align: center;
  }

  .main-content {
    display: flex;
    flex-direction: row; /* Adjusted to row to align elements horizontally */
    align-items: flex-start; /* Align items to the start */
    margin-top: 10px; /* Added margin to the top */
    gap: 20px; /* Gap between the elements */
  }

  .video-stream {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    border-radius: 8px;
  }

  #webcam {
    width: 320px; /* Adjusted width */
    height: 240px; /* Adjusted height */
    border-radius: 8px;
  }

  .plot {
    width: 640px;
    height: 480px;
    background-color: #00e5e5; /* Cyan background for plot */
    display: flex;
    align-items: center;
    justify-content: center;
    color: black;
    font-size: 2rem;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  }

  .controls {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 15px;
  }

  .control-button {
    padding: 10px 30px;
    border: none;
    border-radius: 20px;
    cursor: pointer;
    font-weight: bold;
    transition: background-color 0.3s ease;
    color: white;
    width: 200px; /* Fixed width for consistency */
  }

  .stop-button {
    background-color: #bf2f2f;
  }

  .continue-button {
    background-color: #4caf50;
  }

  .camera-control-button {
    background-color: #808080;
  }

  .victim-button {
    background-color: #ffffff; /* White */
    color: black;
  }

  .exit-button {
    background-color: #000000; /* Black */
    color: white;
  }

  .notification {
    color: #31708f;
    background-color: #d9edf7;
    border-color: #bce8f1;
    padding: 10px;
    border-radius: 4px;
    margin-top: 10px;
    display: none;
  }

  #positionPlot {
    border: 1px solid #000; /* Border to define the canvas area */
  }

</style>
</head>
<body>
<header class="header">
  <h1>CONTROL PANEL</h1>
</header>

<div class="main-content">
  <div class="video-stream">
    <img id="webcam" src="/stream.mjpg" />
    <div id="fpsDisplay" style="text-align:center; margin-top: 10px; font-size: 1.2rem; color: #333;"></div>
  </div>
  <canvas id="positionPlot" class="plot"></canvas>
  <div class="controls">
    <button class="control-button stop-button" onclick="stopRobot()">Stop Movement</button>
    <button class="control-button continue-button" onclick="continueRobot()">Continue Movement</button>
    <button class="control-button camera-control-button" onclick="turnCamera('left')">Camera Turn Left</button>
    <button class="control-button camera-control-button" onclick="turnCamera('right')">Camera Turn Right</button>
    <button class="control-button victim-button" onclick="markVictim()">Tandai Korban</button>
    <button class="control-button exit-button" onclick="markExit()">Tandai Exit</button>
  </div>
</div>

<div class="notification" id="notification"></div>

<script>
  function stopRobot() {
    fetch('/stop', { method: 'POST' })
    .then(response => response.text())
    .then(data => {
        let message = (data === "0") ? 'Robot Has Been Stopped' : 'Unexpected value';
        document.getElementById('notification').textContent = message;
        document.getElementById('notification').style.display = 'block';
    })
    .catch(error => console.error('Error stopping the robot:', error));
  }

  function continueRobot() {
    fetch('/continue', { method: 'POST' })
    .then(response => response.text())
    .then(data => {
        let message = (data === "1") ? 'Robot is Continuing Movement' : 'Unexpected value';
        document.getElementById('notification').textContent = message;
        document.getElementById('notification').style.display = 'block';
    })
    .catch(error => console.error('Error continuing the robot:', error));
  }

  function turnCamera(direction) {
    fetch(`/turn_${direction}`, { method: 'POST' })
    .then(response => response.text())
    .then(data => {
        document.getElementById('notification').textContent = `Camera Turned ${direction}`;
        document.getElementById('notification').style.display = 'block';
    })
    .catch(error => console.error(`Error turning the camera ${direction}:`, error));
  }

  function markVictim() {
    fetch('/mark_victim', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({xpos, ypos})
    })
    .then(response => response.text())
    .then(data => {
        document.getElementById('notification').textContent = 'Korban Ditandai';
        document.getElementById('notification').style.display = 'block';
    })
    .catch(error => console.error('Error marking victim:', error));
  }

  function markExit() {
    fetch('/mark_exit', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({xpos, ypos})
    })
    .then(response => response.text())
    .then(data => {
        document.getElementById('notification').textContent = 'Exit Ditandai';
        document.getElementById('notification').style.display = 'block';
    })
    .catch(error => console.error('Error marking exit:', error));
  }

  const canvas = document.getElementById('positionPlot');
  const ctx = canvas.getContext('2d');
  const padding = 20; // Tambahkan padding
  const gridSize = 30; // Ukuran grid (30x18)
  const scaleX = (canvas.width - 2 * padding) / gridSize; // Skala x sesuai ukuran grid
  const scaleY = (canvas.height - 2 * padding) / 18; // Skala y sesuai ukuran grid
  let xpos = 0;
  let ypos = 0;
  let prevX = xpos;
  let prevY = ypos;
  let positions = []; // Array untuk menyimpan semua posisi
  let victimPositions = []; // Array untuk menyimpan posisi korban
  let exitPositions = []; // Array untuk menyimpan posisi exit

  function drawGrid() {
    ctx.strokeStyle = 'lightgrey';
    ctx.lineWidth = 1;

    // Menggambar garis vertikal
    for (let i = 0; i <= gridSize; i++) {
      const x = padding + i * scaleX;
      ctx.beginPath();
      ctx.moveTo(x, padding);
      ctx.lineTo(x, canvas.height - padding);
      ctx.stroke();
    }

    // Menggambar garis horizontal
    for (let i = 0; i <= 18; i++) {
      const y = padding + i * scaleY;
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(canvas.width - padding, y);
      ctx.stroke();
    }
  }

  function updatePlot(x, y) {
    // Menghapus seluruh kanvas untuk memastikan tidak ada sisa gambar sebelumnya
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Menggambar grid
    drawGrid();

    // Menyimpan posisi saat ini dalam array
    positions.push({ x: prevX, y: prevY, newX: x, newY: y });

    // Menggambar garis biru untuk semua jejak yang disimpan
    ctx.beginPath();
    ctx.strokeStyle = 'blue';
    ctx.lineWidth = 2;
    for (const pos of positions) {
      ctx.moveTo((pos.x + 0.5) * scaleX + padding, (pos.y + 0.5) * scaleY + padding);
      ctx.lineTo((pos.newX + 0.5) * scaleX + padding, (pos.newY + 0.5) * scaleY + padding);
      ctx.stroke();
    }

    // Menggambar titik putih untuk semua posisi korban yang telah disimpan
    for (const pos of victimPositions) {
      ctx.beginPath();
      ctx.arc((pos.x + 0.5) * scaleX + padding, (pos.y + 0.5) * scaleY + padding, 5, 0, 2 * Math.PI);
      ctx.fillStyle = 'white';
      ctx.fill();
    }

    // Menggambar titik hitam untuk semua posisi exit yang telah disimpan
    for (const pos of exitPositions) {
      ctx.beginPath();
      ctx.arc((pos.x + 0.5) * scaleX + padding, (pos.y + 0.5) * scaleY + padding, 5, 0, 2 * Math.PI);
      ctx.fillStyle = 'black';
      ctx.fill();
    }

    // Menggambar titik merah pada posisi saat ini
    ctx.beginPath();
    ctx.arc((x + 0.5) * scaleX + padding, (y + 0.5) * scaleY + padding, 5, 0, 2 * Math.PI);
    ctx.fillStyle = 'red';
    ctx.fill();

    prevX = x;
    prevY = y;
  }

  async function fetchPosition() {
    const response = await fetch('/position');
    const data = await response.json();
    xpos = data.xpos;
    ypos = data.ypos;
    victimPositions = data.victim_positions;
    exitPositions = data.exit_positions;
    updatePlot(xpos, ypos);
  }

  setInterval(fetchPosition, 1000); // Perbarui plot setiap detik

  async function fetchFPS() {
    const response = await fetch('/fps');
    const data = await response.json();
    document.getElementById('fpsDisplay').textContent = `FPS: ${data.fps}`;
  }

  setInterval(fetchFPS, 1000); // Update FPS setiap detik
</script>

</body>
</html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()
        self.start_time = time.time()
        self.frame_count = 0
        self.fps = 0

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

            # Update frame count
            self.frame_count += 1

            # Calculate FPS every second
            current_time = time.time()
            elapsed_time = current_time - self.start_time
            if elapsed_time >= 1.0:
                self.fps = self.frame_count / elapsed_time
                logging.info(f"FPS: {self.fps:.2f}")
                self.start_time = current_time
                self.frame_count = 0

class StreamingHandler(server.BaseHTTPRequestHandler):
    position_data = {"xpos": 0, "ypos": 0}
    victim_positions = []
    exit_positions = []

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))

        elif self.path == '/position':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "xpos": self.position_data["xpos"],
                "ypos": self.position_data["ypos"],
                "victim_positions": self.victim_positions,
                "exit_positions": self.exit_positions
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
       
        elif self.path == '/fps':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"fps": output.fps}
            self.wfile.write(json.dumps(response).encode('utf-8'))
       
        else:
            self.send_error(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/stop':
            print('Robot Berhenti')  # Log the stop command as received
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"0")  # Return value 0 for stop
            pause_movement()  # Panggil fungsi pause_movement dari robot_control.py
        elif self.path == '/continue':
            print('Robot Berjalan')  # Log the continue command as received
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"1")  # Return value 1 for continue
            continue_movement()  # Panggil fungsi continue_movement dari robot_control.py
        elif self.path == '/turn_right':
            print('Kamera Putar Kanan')  # Log the turn right command as received
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Turn Right command received")
            turn_servo("right")
        elif self.path == '/turn_left':
            print('Kamera Putar Kiri')  # Log the turn left command as received
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Turn Left command received")
            turn_servo("left")
        elif self.path == '/mark_victim':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            xpos = data.get("xpos", self.position_data["xpos"])
            ypos = data.get("ypos", self.position_data["ypos"])
            self.victim_positions.append({"x": xpos, "y": ypos})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Victim marked")
        elif self.path == '/mark_exit':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            xpos = data.get("xpos", self.position_data["xpos"])
            ypos = data.get("ypos", self.position_data["ypos"])
            self.exit_positions.append({"x": xpos, "y": ypos})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Exit marked")
        elif self.path == '/update_position':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            self.position_data["xpos"] = data.get("xpos", self.position_data["xpos"])
            self.position_data["ypos"] = data.get("ypos", self.position_data["ypos"])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Position updated")
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(transform=Transform(hflip=True, vflip=True), main={"size": (640, 480)}))
output = StreamingOutput()
picam2.start_recording(MJPEGEncoder(), FileOutput(output))

def start_interface_server():
    try:
        address = ('192.168.153.222', 8888)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        picam2.stop_recording()

if __name__ == '__main__':
    start_interface_server()
