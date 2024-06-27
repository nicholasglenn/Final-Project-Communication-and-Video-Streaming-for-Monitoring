import RPi.GPIO as GPIO
import time
import threading  # Tambahkan ini untuk mengimpor modul threading

# Define GPIO to use for the servo
SERVO_PIN = 12

# Initialize GPIO for servo control
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)  # Nonaktifkan peringatan GPIO
GPIO.setup(SERVO_PIN, GPIO.OUT)
pwm_servo = GPIO.PWM(SERVO_PIN, 50)  # 50Hz (20ms PWM period)
pwm_servo.start(0)

# Initial servo angle
current_angle = 90

def set_angle(angle):
    duty = 2 + (angle / 18)
    GPIO.output(SERVO_PIN, True)
    pwm_servo.ChangeDutyCycle(duty)
    time.sleep(1)
    GPIO.output(SERVO_PIN, False)
    pwm_servo.ChangeDutyCycle(0)

# Initialize the servo to the center position
set_angle(current_angle)

def turn_servo(direction):
    global current_angle
    if direction == "right":
        current_angle = min(current_angle + 90, 180)
    elif direction == "left":
        current_angle = max(current_angle - 90, 0)
    set_angle(current_angle)

pause_event = threading.Event()  # Tambahkan ini untuk mendefinisikan pause_event

def pause_movement():
    pause_event.set()
    print("Pause movement")

def continue_movement():
    pause_event.clear()
    print("Continue movement")
