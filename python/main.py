import time
from arduino_app_lab import Bridge # Middleware for MCU communication
from arduino_bricks import web_ui, ai_model # Accessing injected Bricks

def on_hardware_trigger(sensor_value):
    #print(f"Sensor threshold hit: {sensor_value}. Running AI Analysis...")
    
    # 1. Grab data/frame from the AI Brick (e.g., camera feed or data arrays)
    #inference = ai_model.get_latest_inference() 
    
    # Example structure: {"label": "Equipment_A", "confidence": 0.94}
    #classification = inference.get("label", "Unknown")
    #confidence = inference.get("confidence", 0.0)

    # 2. Package data for the Web Interface
    payload = {
        "sensor_reading": 1,
        "ai_result": 2,
        "confidence": 3,
        "timestamp": time.strftime("%H:%M:%S")
    }
    
    # 3. Stream data to the frontend Web UI
    web_ui.emit("data_update", payload)

def main():
    print("AI Data Analyzer Pipeline Starting...")
    
    # Listen to data variables shared by the real-time C++ MCU sketch
    Bridge.register_callback("raw_sensor_event", on_hardware_trigger)
    
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
