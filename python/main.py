from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

def update_sensor_data(data):
    ui.send_message("update", data)

Bridge.provide("baseline", update_sensor_data)

App.run()