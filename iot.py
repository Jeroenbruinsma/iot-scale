#! /usr/bin/python3

import time
import sys
import RPi.GPIO as GPIO
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import time as t
import json
from gpiozero import CPUTemperature
import datetime

EMULATE_HX711=False

referenceUnit = 359.5397391

if not EMULATE_HX711:
    import RPi.GPIO as GPIO
    from hx711 import HX711
else:
    from emulated_hx711 import HX711


def cleanAndExit():
    print("Cleaning...")
    if not EMULATE_HX711:
        GPIO.cleanup()
        
    print("Bye!")
    sys.exit()


def getserial():
  # Extract serial from cpuinfo file
  cpuserial = "0000000000000000"
  try:
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:6]=='Serial':
        cpuserial = line[10:26]
    f.close()
  except:
    cpuserial = "ERROR000000000"
 
  return cpuserial

def on_message_received(topic, payload, **kwargs):
    print("Received message from topic '{}': {}".format(topic, payload))
    print("args", kwargs)



# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


# Define ENDPOINT, CLIENT_ID, PATH_TO_CERT, PATH_TO_KEY, PATH_TO_ROOT, MESSAGE, TOPIC, and RANGE
ENDPOINT = "a1bqva80g2zl30-ats.iot.eu-central-1.amazonaws.com"
CLIENT_ID = "PiScale"
PATH_TO_CERT = "/home/pi/hx711py/cert.pem"
PATH_TO_KEY = "/home/pi/hx711py/private.key"
PATH_TO_ROOT = "/home/pi/hx711py/root-CA.crt"
MESSAGE = "Hello World"
TOPIC = "test/testing" #not used
RANGE = 20


# Spin up resources
event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
mqtt_connection = mqtt_connection_builder.mtls_from_path(endpoint=ENDPOINT,cert_filepath=PATH_TO_CERT,pri_key_filepath=PATH_TO_KEY,client_bootstrap=client_bootstrap,ca_filepath=PATH_TO_ROOT,client_id=CLIENT_ID,clean_session=False,keep_alive_secs=6)
print("Connecting to {} with client ID '{}'...".format(ENDPOINT, CLIENT_ID))
# Make the connect() call
connect_future = mqtt_connection.connect()
# Future.result() waits until a result is available
connect_future.result()
print("Connected!")
# Publish message to server desired number of times.
print('Begin Publish')
# for i in range (RANGE):

# disconnect_future = mqtt_connection.disconnect()
# disconnect_future.result()

hx = HX711(5, 6)
GPIO.setup(13, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# I've found out that, for some reason, the order of the bytes is not always the same between versions of python, numpy and the hx711 itself.
# Still need to figure out why does it change.
# If you're experiencing super random values, change these values to MSB or LSB until to get more stable values.
# There is some code below to debug and log the order of the bits and the bytes.
# The first parameter is the order in which the bytes are used to build the "long" value.
# The second paramter is the order of the bits inside each byte.
# According to the HX711 Datasheet, the second parameter is MSB so you shouldn't need to modify it.
hx.set_reading_format("MSB", "MSB")

# HOW TO CALCULATE THE REFFERENCE UNIT
# To set the reference unit to 1. Put 1kg on your sensor or anything you have and know exactly how much it weights.
# In this case, 92 is 1 gram because, with 1 as a reference unit I got numbers near 0 without any weight
# and I got numbers around 184000 when I added 2kg. So, according to the rule of thirds:
# If 2000 grams is 184000 then 1000 grams is 184000 / 2000 = 92.
#hx.set_reference_unit(113)

hx.set_reference_unit(referenceUnit)

hx.reset()

hx.tare()
print("Tare done! Add weight now...")

subscribe_future, packet_id = mqtt_connection.subscribe(
    topic="scale/tare",
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_message_received
)
subscribe_result = subscribe_future.result()
print(subscribe_result)



while True:
    try:
        # These three lines are usefull to debug wether to use MSB or LSB in the reading formats
        # for the first parameter of "hx.set_reading_format("LSB", "MSB")".
        # Comment the two lines "val = hx.get_weight(5)" and "print val" and uncomment these three lines to see what it prints.
        
        # np_arr8_string = hx.get_np_arr8_string()
        # binary_string = hx.get_binary_string()
        # print binary_string + " " + np_arr8_string
        
        # Prints the weight. Comment if you're debbuging the MSB and LSB issue.
        val = hx.get_weight(15)
        print(val)
        timeStamp = datetime.datetime.now()
        cpu = CPUTemperature()
        temp = str(cpu.temperature)
        serial = getserial()
        message = {"deviceId": str(serial), "timestamp": str(timeStamp) ,"weight" : val, "temp": temp}
        mqtt_connection.publish(topic="scale/weight", payload=json.dumps(message), qos=mqtt.QoS.AT_LEAST_ONCE)
        print("Published: '" + json.dumps(message) + "' to the topic: " + "'scale/weight'")
        t.sleep(5)
        print(GPIO.input(13))
        print(cpu.temperature)
        #mqtt_connection.publish(topic="scale/temp", payload=json.dumps({"temp": temp}), qos=mqtt.QoS.AT_LEAST_ONCE)

        hx.power_down()
        hx.power_up()
        time.sleep(10)

    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()
