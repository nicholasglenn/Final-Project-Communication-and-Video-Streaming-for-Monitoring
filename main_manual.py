# main_manual.py
# Main Control of Robot
# TA 08

import RPi.GPIO as GPIO
import time
import smbus
import threading
import json
import requests
from http.server import HTTPServer
from interface_akhir import StreamingServer, StreamingHandler, picam2, output
from robot_control import pause_event, pause_movement, continue_movement

from sensor_ultrasonik import measure_distance
from motor_driver import forward, backward, left, right, stop
from BSA_LimMove import searchzero, nextmove
import sensor_imu

# Set mode pin GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)  # Disable GPIO warnings

############################################## IMU ####################################################
# Inisialisasi alamat I2C dan register MPU6050
MPU6050_ADDR = 0x68
PWR_MGMT_1 = 0x6B
GYRO_CONFIG = 0x1B  # Register untuk konfigurasi gyro
GYRO_ZOUT_H = 0x47
GYRO_ZOUT_L = 0x48

# Inisialisasi untuk akeselerometer
ACCEL_CONFIG = 0x1C
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F

# Konfigurasi bus I2C
bus = smbus.SMBus(1)

# Variable global untuk menyimpan sudut rotasi z
rotation_angle_z = 0.0

# Variable global untuk menyimpan nilai offset yang dihasilkan dari kalibrasi
gyro_offset_z = 0.0

# Variabel global untuk menyimpan offset kalibrasi akselerometer
accel_offset_x = 0
accel_offset_y = 0
accel_offset_z = 0

############################################## ULTRASONIC ############################################
# Tentukan pin GPIO untuk masing-masing sensor ultrasonic
FRONT_TRIG_PIN = 4
FRONT_ECHO_PIN = 18
RIGHT_TRIG_PIN = 23
RIGHT_ECHO_PIN = 24
LEFT_TRIG_PIN = 27
LEFT_ECHO_PIN = 22
BACK_TRIG_PIN = 10
BACK_ECHO_PIN = 9

# Setup pin GPIO untuk setiap sensor
GPIO.setup(FRONT_TRIG_PIN, GPIO.OUT)
GPIO.setup(FRONT_ECHO_PIN, GPIO.IN)
GPIO.setup(BACK_TRIG_PIN, GPIO.OUT)
GPIO.setup(BACK_ECHO_PIN, GPIO.IN)
GPIO.setup(RIGHT_TRIG_PIN, GPIO.OUT)
GPIO.setup(RIGHT_ECHO_PIN, GPIO.IN)
GPIO.setup(LEFT_TRIG_PIN, GPIO.OUT)
GPIO.setup(LEFT_ECHO_PIN, GPIO.IN)

############################################## MOTOR DRIVER ##########################################
# Define GPIO pins for motor driver
ENA = 13
ENB = 19
IN1 = 25
IN2 = 8
IN3 = 7
IN4 = 11

# Setup GPIO pins for motor driver
GPIO.setup(ENA, GPIO.OUT)
GPIO.setup(ENB, GPIO.OUT)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

# Set initial motor speed (PWM)
pwm_a = GPIO.PWM(ENA, 1000)
pwm_b = GPIO.PWM(ENB, 1000)
pwm_a.start(0)
pwm_b.start(0)

############################################## ODOMETRI #############################################

############################################## Main Control ##########################################
# Variabel Event untuk memberi sinyal kepada thread untuk berhenti atau melanjutkan

# Arena Assignment
arenamove = [[[0 for i in range(4)] for j in range(30)] for k in range(18)]
arena = [[0 for i in range(30)] for j in range(18)]
movepair = [2, 3, 0, 1]
xpos = 0
ypos = 0
arena[ypos][xpos] = 1
lastaction = 1
for i in range(14):
    for j in range(30):
        if (i == 0):
            arenamove[i][j][0] = 6
        if (i == 17):
            arenamove[i][j][2] = 6
        if (j == 0):
            arenamove[i][j][3] = 6
        if (j == 29):
            arenamove[i][j][1] = 6

# xmax = 15
# ymax = 9
arah = ["atas","kanan","bawah","kiri"]
# ket : 0 = Atas , 1 = Kanan, 2 = Bawah, 3 = kiri ; relatif terhadap posisi awal robot; pair adalah varible yang berlawanan dengan keadaannya

def move_forward():
    sensor_imu.rotation_angle_z = 0
    pwm_a.ChangeDutyCycle(100)
    pwm_b.ChangeDutyCycle(100)
    if sensor_imu.pitch >= 25: # cek kemiringan pitch robot (jalan menanjak)
        move_backward()
        time.sleep(0.5)
    else:
        forward(IN1, IN2, IN3, IN4)
        time.sleep(0.76)
        stop(IN1, IN2, IN3, IN4)
        time.sleep(0.5)
       
def move_backward():
    pwm_a.ChangeDutyCycle(100)
    pwm_b.ChangeDutyCycle(100)
    backward(IN1, IN2, IN3, IN4)
    time.sleep(0.8)
   
def move_right():
    pwm_a.ChangeDutyCycle(100)
    pwm_b.ChangeDutyCycle(100)
    while sensor_imu.rotation_angle_z > -65:
        right(IN1, IN2, IN3, IN4)
        time.sleep(0.001)
    stop(IN1, IN2, IN3, IN4)
    time.sleep(1)

def move_left():
    pwm_a.ChangeDutyCycle(100)
    pwm_b.ChangeDutyCycle(100)
    while sensor_imu.rotation_angle_z < 65:
        left(IN1, IN2, IN3, IN4)
        time.sleep(0.001)
    stop(IN1, IN2, IN3, IN4)
    time.sleep(1)
   
def turn_back():
    pwm_a.ChangeDutyCycle(100)
    pwm_b.ChangeDutyCycle(100)
    while sensor_imu.rotation_angle_z < 180:
        left(IN1, IN2, IN3, IN4)
        time.sleep(0.001)
    stop(IN1, IN2, IN3, IN4)
    time.sleep(5)

# Ultrasonic Sensor
def lookfront():
    output = 0
    front_distance  = measure_distance(FRONT_TRIG_PIN, FRONT_ECHO_PIN)
    print(f"jarak depan: {front_distance}")
    if front_distance < 35:
        output = 6
    return output
   
def lookright():
    output = 0
    right_distance  = measure_distance(RIGHT_TRIG_PIN, RIGHT_ECHO_PIN)
    print(f"jarak kanan: {right_distance}")
    if right_distance < 50:
        output = 6
    return output
   
def lookleft():
    output = 0
    left_distance   = measure_distance(LEFT_TRIG_PIN, LEFT_ECHO_PIN)
    print(f"jarak kiri: {left_distance}")
    if left_distance < 50:
        output = 6
    return output
   
def lookbehind():
    output = 0
    back_distance   = measure_distance(BACK_TRIG_PIN, BACK_ECHO_PIN)
    print(f"jarak belakang: {back_distance}")
    if back_distance < 35:
        output = 6
    return output

# Cek sekitar
def checkaround(movepart, lastaction):
    if (lastaction == 0):
        if (movepart[0] == 0):
            movepart[0] = lookfront()
        if (movepart[1] == 0):
            movepart[1] = lookright()
        if (movepart[2] == 0):
            movepart[2] = lookbehind()
        if (movepart[3] == 0):
            movepart[3] = lookleft()
    if (lastaction == 1):
        if (movepart[0] == 0):
            movepart[0] = lookleft()
        if (movepart[1] == 0):
            movepart[1] = lookfront()
        if (movepart[2] == 0):
            movepart[2] = lookright()
        if (movepart[3] == 0):
            movepart[3] = lookbehind()
    if (lastaction == 2):
        if (movepart[0] == 0):
            movepart[0] = lookbehind()
        if (movepart[1] == 0):
            movepart[1] = lookleft()
        if (movepart[2] == 0):
            movepart[2] = lookfront()
        if (movepart[3] == 0):
            movepart[3] = lookright()
    if (lastaction == 3):
        if (movepart[0] == 0):
            movepart[0] = lookright()
        if (movepart[1] == 0):
            movepart[1] = lookbehind()
        if (movepart[2] == 0):
            movepart[2] = lookleft()
        if (movepart[3] == 0):
            movepart[3] = lookfront()
       
def pergerakan_robot(lastaction, nextaction, movepair):
    if lastaction == nextaction:  
        move_forward()
    elif (lastaction == 3 and nextaction == 0) :
        move_right()
        move_forward()
    elif (lastaction == 0 and nextaction == 3) :
        move_left()
        move_forward()
    else:
        if nextaction != 5:
            if lastaction != movepair[nextaction]:
                if nextaction > lastaction:
                    move_right()
                    move_forward()
                else:
                    move_left()
                    move_forward()
            else:
                turn_back()
                move_forward()
    stop(IN1, IN2, IN3, IN4)
    time.sleep(0.00001)

def update_position_on_interface(xpos, ypos):
    url = "http://192.168.153.222:8888/update_position"  # Pastikan IP ini benar
    data = {"xpos": xpos, "ypos": ypos}
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print(f"Position updated: x={xpos}, y={ypos}")
        else:
            print("Failed to update position on interface")
    except Exception as e:
        print(f"Error updating position: {e}")

def cleanup():
    # Matikan GPIO
    GPIO.cleanup()

def start_server():
    address = ('192.168.153.222', 8888)
    server = StreamingServer(address, StreamingHandler)
    print("Starting server at http://192.168.153.222:8888")
    server.serve_forever()

if __name__ == "__main__":
    try:
        # Start the interface server in a separate thread
        server_thread = threading.Thread(target=start_server)
        server_thread.daemon = True
        server_thread.start()

        # Inisialisasi MPU6050
        bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0)
        # Konfigurasi gyro ; ket : 0b11 untuk 2000dps
        sensor_imu.set_gyro_scale(0b11)  
        # 0 untuk skala +-2g
        sensor_imu.set_accel_fsr(0)

        print("Kalibrasi...")
        # Kalibrasi gyro
        sensor_imu.calibrate_gyro()
        print("Kalibrasi selesai")

        # Buat thread untuk mengukur sudut rotasi z secara kontinu
        dt = 0.07  # Interval waktu untuk pengukuran (misalnya, 0.1 detik)
        gyro_thread = threading.Thread(target=sensor_imu.integrate_gyro_data, args=(pause_event, dt,))
        gyro_thread.daemon = True
        gyro_thread.start()

        # Mulai thread untuk mencetak sudut pitch dan roll secara kontinu
        print_thread = threading.Thread(target=sensor_imu.get_pitch_and_roll, args=(pause_event, ACCEL_XOUT_H,ACCEL_YOUT_H,ACCEL_ZOUT_H,))
        print_thread.daemon = True
        print_thread.start()
       
        # Bergerak
        while True:
            if pause_event.is_set():  # Periksa apakah pergerakan dijeda
                continue
            stop(IN1, IN2, IN3, IN4)
            checkaround(arenamove[ypos][xpos], lastaction)
            time.sleep(0.1)
            nextaction = nextmove(lastaction, arena, arenamove, xpos, ypos)
            if nextaction == 5 :
                print(arenamove[ypos][xpos])
            if (nextaction == 0):
                arenamove[ypos][xpos][nextaction] = 1
                pergerakan_robot(lastaction, nextaction, movepair)
                ypos -= 1
                arena[ypos][xpos] = 1
                arenamove[ypos][xpos][movepair[nextaction]] = 1
                # Update posisi pada interface
                update_position_on_interface(xpos, ypos)
            elif (nextaction == 1):
                arenamove[ypos][xpos][nextaction] = 1
                pergerakan_robot(lastaction, nextaction, movepair)
                xpos += 1
                arena[ypos][xpos] = 1
                arenamove[ypos][xpos][movepair[nextaction]] = 1
                # Update posisi pada interface
                update_position_on_interface(xpos, ypos)
            elif (nextaction == 2):
                arenamove[ypos][xpos][nextaction] = 1
                pergerakan_robot(lastaction, nextaction, movepair)
                ypos += 1
                arena[ypos][xpos] = 1
                arenamove[ypos][xpos][movepair[nextaction]] = 1
                # Update posisi pada interface
                update_position_on_interface(xpos, ypos)
            elif (nextaction == 3):
                arenamove[ypos][xpos][nextaction] = 1
                pergerakan_robot(lastaction, nextaction, movepair)
                xpos -= 1
                arena[ypos][xpos] = 1
                arenamove[ypos][xpos][movepair[nextaction]] = 1
                # Update posisi pada interface
                update_position_on_interface(xpos, ypos)
            else:
                backtrack = searchzero(arena, arenamove, xpos, ypos)
                if (backtrack == "reject"):
                    break
                else:
                    for i in backtrack:
                        if (i == 0):
                            arenamove[ypos][xpos][i] = 1
                            pergerakan_robot(lastaction, nextaction, movepair)
                            ypos -= 1
                            arena[ypos][xpos] = 1
                            arenamove[ypos][xpos][movepair[i]] = 1
                            # Update posisi pada interface
                            update_position_on_interface(xpos, ypos)
                        elif (i == 1):
                            arenamove[ypos][xpos][i] = 1
                            pergerakan_robot(lastaction, nextaction, movepair)
                            xpos += 1
                            arena[ypos][xpos] = 1
                            arenamove[ypos][xpos][movepair[i]] = 1
                            # Update posisi pada interface
                            update_position_on_interface(xpos, ypos)
                        elif (i == 2):
                            arenamove[ypos][xpos][i] = 1
                            pergerakan_robot(lastaction, nextaction, movepair)
                            ypos += 1
                            arena[ypos][xpos] = 1
                            arenamove[ypos][xpos][movepair[i]] = 1
                            # Update posisi pada interface
                            update_position_on_interface(xpos, ypos)
                        else:
                            arenamove[ypos][xpos][i] = 1
                            pergerakan_robot(lastaction, nextaction, movepair)
                            xpos -= 1
                            arena[ypos][xpos] = 1
                            arenamove[ypos][xpos][movepair[i]] = 1
                            # Update posisi pada interface
                            update_position_on_interface(xpos, ypos)
                        checkaround(arenamove[ypos][xpos], i)
                        nextaction = i
            lastaction = nextaction

#             # Update posisi pada interface
#             update_position_on_interface(xpos, ypos)
                       
    except KeyboardInterrupt:
        # Tangkap KeyboardInterrupt (Ctrl+C) untuk membersihkan GPIO
        pause_event.set()
        cleanup()
