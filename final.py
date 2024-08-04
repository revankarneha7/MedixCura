from serial.tools import list_ports
import os
import csv
from flask import Flask, render_template, request, jsonify
import cv2
from PIL import Image
import pytesseract
from fuzzywuzzy import fuzz
import datetime
import threading
import time
import pygame
import pyttsx3
import serial



app = Flask(__name__)

# Find the serial port
port = None
ports = list(list_ports.comports())
for p in ports:
    if 'COM6' in p.device:  # Replace 'COM3' with the name of your serial port
        port = p.device
        break

# Open the serial port
ser = serial.Serial(port, baudrate=115200)


# Path to Tesseract executable (change it according to your system)
pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

# Load medicine data from a CSV file
medicine_data = {}
with open('medicine_data.csv', 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        medicine_data[row['medicine']] = row['description']

# Load disease data from a CSV file
disease_data = {}
with open('disease_data.csv', 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        disease_data[row['disease']] = row['symptoms']

alarms = {}  # Dictionary to store alarms
is_alarm_triggered = False  # Flag to indicate if alarm is triggered

# Route for the homepage
@app.route('/')
def home():
    return render_template('test_dum.html')

@app.route('/command',methods=['POST'])
def command():
    data=request.get_json()
    command=data['command']
    ser.write(command.encode())
    return '', 200
    

@app.route('/data')
def get_data():
    if ser.in_waiting > 0:
        data = ser.readline().decode().strip()
        return jsonify(data=data)
    else:
        time.sleep(2)
        return jsonify(data='No data available')

@app.route('/capture', methods=['POST'])
def capture():
    # Open camera
    camera = cv2.VideoCapture(0)

    while True:
        # Read a frame from the camera
        ret, frame = camera.read()
        if not ret:
            print("failed to grab frame")
            pyobj=pyttsx3.init()
            pyobj.say("failed to grab frame")
            pyobj.runAndWait() 
            break

        # Display the frame
        cv2.imshow("Camera", frame)

        # Check for key press
        key = cv2.waitKey(1)
        
        if key == 27:  # ESC key to exit
            break
        elif key == 32:  # Space key to capture and recognize text
            # Save the captured frame as an image file
            image_path = 'captured_image.png'
            cv2.imwrite(image_path, frame)

            # Perform text recognition on the captured image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            os.remove(image_path)  # Delete the temporary image file

            if not text:
                # Release the camera
                camera.release()
                cv2.destroyAllWindows()
                pyobj=pyttsx3.init()
                pyobj.say("No text detected. No medicine found.")
                pyobj.runAndWait()  
                return "No text detected. No medicine found."

            # Find the best matching medicine description
            best_match = None
            highest_similarity = 0
            for medicine in medicine_data:
                similarity = fuzz.token_set_ratio(text.lower(), medicine.lower())
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    best_match = medicine
            print(best_match)
            if best_match is not None:
                # Release the camera
                camera.release()
                cv2.destroyAllWindows()
                pyobj=pyttsx3.init()
                pyobj.say("{} :  {}".format(best_match, medicine_data[best_match]))
                pyobj.runAndWait() 
                return "{} :  {}".format(best_match, medicine_data[best_match])

    # Release the camera
    camera.release()
    cv2.destroyAllWindows()
    pyobj=pyttsx3.init()
    pyobj.say("Failed to capture")
    pyobj.runAndWait()  
    return "Failed to capture."


@app.route('/set_alarm', methods=['POST'])
def set_alarm():
    medicine_name = request.form['medicine_name']
    alarm_time = request.form['alarm_time']

    # Validate the alarm time format
    try:
        alarm_hour, alarm_minute = map(int, alarm_time.split(':'))
        now = datetime.datetime.now()
        alarm_datetime = datetime.datetime(now.year, now.month, now.day, alarm_hour, alarm_minute)
    except ValueError:
        pyobj=pyttsx3.init()
        pyobj.say("Invalid alarm time format. Please enter the time in HH:MM format.")
        pyobj.runAndWait() 
        return "Invalid alarm time format. Please enter the time in HH:MM format."

    # Check if the alarm time is in the past
    if alarm_datetime < datetime.datetime.now():
        pyobj=pyttsx3.init()
        pyobj.say("Invalid alarm time. Please choose a time in the future.")
        pyobj.runAndWait() 
        return "Invalid alarm time. Please choose a time in the future."

    # Store the alarm in the dictionary
    alarms[medicine_name] = alarm_datetime
    pyobj=pyttsx3.init()
    pyobj.say("Alarm set for {} at {}.".format(medicine_name, alarm_time))
    pyobj.runAndWait()   
    return "Alarm set for {} at {}.".format(medicine_name, alarm_time) 



pygame.mixer.init()  # Initialize pygame mixer
alarm_sound = pygame.mixer.Sound(r'C:\Users\Lohit\Desktop\New_final\alarm_sound.mp3')


def check_alarm():
    global is_alarm_triggered
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M")
        current_hour, current_minute = map(int, current_time.split(':'))
        for medicine_name, alarm_time in alarms.items():
            alarm_hour = alarm_time.hour
            alarm_minute = alarm_time.minute
            if current_hour == alarm_hour and current_minute == alarm_minute:
                if not is_alarm_triggered:
                    is_alarm_triggered = True
                    update_alarm_csv(medicine_name, alarm_time)
                    alarm_sound.play(maxtime=5000)  # Play the alarm sound for 3 seconds (3000 milliseconds)

                    # Start a timer to stop the alarm after 3 seconds
                    threading.Timer(5, stop_alarm).start()

                    # Speak "take medicine" message
                    speak_message("Take medicine")
                    time.sleep(1)
                break
        else:
            is_alarm_triggered = False
        # Sleep for a while before checking the alarms again
        time.sleep(1)

def stop_alarm():
    alarm_sound.stop()

def speak_message(message):
    pyobj = pyttsx3.init()
    pyobj.say(message)
    pyobj.runAndWait()




def update_alarm_csv(medicine_name, alarm_datetime):
    csv_file = 'alarms.csv'
    fieldnames = ['Medicine', 'Timestamp']

    # Check if the CSV file exists
    file_exists = os.path.isfile(csv_file)

    # Open the CSV file in append mode
    with open(csv_file, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write the header if the file is newly created
        if not file_exists:
            writer.writeheader()

        # Write the alarm data
        writer.writerow({'Medicine': medicine_name, 'Timestamp': alarm_datetime})

def process_temperature_data(temperature):
    # Define threshold for fever detection
    fever_threshold = 38.0  # Celsius

    if temperature > fever_threshold:
        return "Fever detected"
    else:
        return "No fever"

# Sample function to process pulse sensor data
def process_pulse_data(pulse_rate):
    # Define normal range for pulse rate
    normal_pulse_range = (60, 100)  # Beats per minute

    if pulse_rate < normal_pulse_range[0] or pulse_rate > normal_pulse_range[1]:
        return "Abnormal pulse rate detected"
    else:
        return "Normal pulse rate"

# Sample function to process blood pressure sensor data
def process_blood_pressure_data(systolic, diastolic):
    # Define normal range for blood pressure
    normal_systolic_range = (90, 120)  # mmHg
    normal_diastolic_range = (60, 80)  # mmHg

    if systolic < normal_systolic_range[0] or systolic > normal_systolic_range[1]:
        return "Abnormal systolic pressure detected"
    elif diastolic < normal_diastolic_range[0] or diastolic > normal_diastolic_range[1]:
        return "Abnormal diastolic pressure detected"
    else:
        return "Normal blood pressure"

# Route to receive sensor data and diagnose fever and cold
@app.route('/diagnose', methods=['POST'])
def diagnose():
    # Assuming the data is received in JSON format
    data = request.json

    temperature = data.get('temperature')
    pulse_rate = data.get('pulse_rate')
    systolic_pressure = data.get('systolic_pressure')
    diastolic_pressure = data.get('diastolic_pressure')

    # Process sensor data
    temperature_result = process_temperature_data(temperature)
    pulse_result = process_pulse_data(pulse_rate)
    bp_result = process_blood_pressure_data(systolic_pressure, diastolic_pressure)

    # Combine results for diagnosis
    diagnosis = {
        "temperature": temperature_result,
        "pulse_rate": pulse_result,
        "blood_pressure": bp_result
    }

    return jsonify(diagnosis)


if __name__ == '__main__':
    # Start a separate thread to check the alarms
    alarm_thread = threading.Thread(target=check_alarm)
    alarm_thread.daemon = True  # Set the thread as daemon so it will be terminated when the main program exits
    alarm_thread.start()

    # Run the Flask app
    app.run()