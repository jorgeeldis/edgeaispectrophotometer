from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import json

ui = WebUI()

def process_array(val1):
    # Reassemble them into a python list
    my_list = [val1]
    print(f"Received Array Data: {my_list}")

# Register the listener
Bridge.provide("sendChannels", process_array)

def loop():
    pass

App.run(user_loop=loop)