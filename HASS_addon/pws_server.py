#!/usr/bin/env python3
import os
import http.server
import socketserver
import paho.mqtt.client as mqtt
from urllib.parse import urlparse
from urllib.parse import parse_qs
import json
import sys
from datetime import datetime

#WEBSERVER PORT
WEBSERVER_PORT = 8087

# MQTT Client configuration
MQTT_BROKER_HOST=os.environ['MQTT_BROKER_HOST']
MQTT_BROKER_PORT=int(os.environ['MQTT_BROKER_PORT'])
MQTT_USERNAME=os.environ['MQTT_USERNAME']
MQTT_PASSWORD=os.environ['MQTT_PASSWORD']

MQTT_CLIENT_ID    = "weatherstation"
MQTT_TOPIC_PREFIX = "homeassistant"
MQTT_TOPIC = MQTT_TOPIC_PREFIX + "/weatherstation"

def publish_discovery(client, sensor_name, unit, device_class, has_individual_availability=True, value_template="{{value}}"):
    config = {
        "name": f"Weather Station {sensor_name}",
        "state_topic": f"{MQTT_TOPIC}/{sensor_name}",
        "device_class": device_class,
        "unique_id": f"weather_station_{sensor_name}",
        "device": {
            "identifiers": ["weather_station_1"],
            "name": "Weather Station",
            "model": "Weather Station",
            "manufacturer": "Custom"
        }
    }
    
    # Only add unit_of_measurement if it's not None
    if unit is not None:
        config["unit_of_measurement"] = unit
        
    # Special configuration for timestamp sensor
    if device_class == "timestamp":
        config["entity_category"] = "diagnostic"
        
    if has_individual_availability:
        config["availability"] = [
            {
                "topic": f"{MQTT_TOPIC_PREFIX}/status",
                "payload_available": "Online",
                "payload_not_available": "Offline"
            },
            {
                "topic": f"{MQTT_TOPIC}/{sensor_name}/availability",
                "payload_available": "online",
                "payload_not_available": "offline"
            }
        ]
        config["availability_mode"] = "all"
    else:
        config["availability_topic"] = f"{MQTT_TOPIC_PREFIX}/status"
        config["payload_available"] = "Online"
        config["payload_not_available"] = "Offline"
        
    discovery_topic = f"{MQTT_TOPIC_PREFIX}/sensor/weather_station/{sensor_name}/config"
    client.publish(discovery_topic, json.dumps(config), retain=True)

def setup_discovery(client):
    # Add timestamp sensor discovery
    publish_discovery(client, "last_update", None, "timestamp", has_individual_availability=False)
    
    # Temperature sensors
    publish_discovery(client, "temperature_out", "°C", "temperature")
    publish_discovery(client, "temperature_in", "°C", "temperature")
    publish_discovery(client, "humidity_out", "%", "humidity")
    publish_discovery(client, "humidity_in", "%", "humidity")
    publish_discovery(client, "barometric_pressure", "hPa", "pressure")
    publish_discovery(client, "abs_barometric_pressure", "hPa", "pressure")
    publish_discovery(client, "wind_speed", "m/s", "wind_speed")
    publish_discovery(client, "wind_gust_speed", "m/s", "wind_speed")
    publish_discovery(client, "wind_direction", "°", None)
    publish_discovery(client, "rain_rate", "mm/h", None)
    publish_discovery(client, "rain_daily", "mm", None)
    publish_discovery(client, "rain_weekly", "mm", None)
    publish_discovery(client, "rain_monthly", "mm", None)
    publish_discovery(client, "solar_radiation", "W/m²", "irradiance")
    publish_discovery(client, "uv_index", "UV index", None)
    publish_discovery(client, "dewpoint", "°C", "temperature")
    publish_discovery(client, "low_battery", "%", "battery")

def on_connect(client, userdata, flags, rc):
    status = "✅ Connected" if rc == 0 else f"❌ Connection failed (code {rc})"
    print(f"{status} to MQTT broker at {MQTT_BROKER_HOST}")
    if rc == 0:
        # Publish Online status for the service itself
        client.publish(MQTT_TOPIC_PREFIX+"/status", payload="Online", qos=1, retain=True)
        setup_discovery(client)

def on_disconnect(client, userdata, flags, rc):
    print("❌ Disconnected from MQTT broker")

def publish(client, topic, msg, retain=False):
    if not client.is_connected():
        print("❌ Client not connected - cannot publish data")
        return
        
    result = client.publish(topic, msg, retain=retain)
    if result[0] == 0:
        print(f"✅ {topic}: {msg}")
    else:
        print(f"❌ Failed to publish to {topic}")
    
    sys.stdout.flush()

# set up mqtt client
client = mqtt.Client(client_id=MQTT_CLIENT_ID)
if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME,MQTT_PASSWORD)
    print("Username and password set.")
client.will_set(MQTT_TOPIC_PREFIX+"/status", payload="Offline", qos=1, retain=True)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.connect(MQTT_BROKER_HOST, port=MQTT_BROKER_PORT, keepalive=60)
client.loop_start()

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def parse_wu_data(query_components):
        data_array = {}
        
        def get_valid_val(key):
            if key in query_components:
                val = query_components[key][0]
                if val == '-9999' or val == '-9999.0':
                    return None
                return val
            return None

        # tempf
        val = get_valid_val('tempf')
        if 'tempf' in query_components:
            data_array['Temperature_out_[C]'] = round((float(val)-32) * 5/9,1) if val is not None else None
            
        # humidity
        val = get_valid_val('humidity')
        if 'humidity' in query_components:
            data_array['Humidity_out_[%]'] = int(val) if val is not None else None
            
        # dewptf
        val = get_valid_val('dewptf')
        if 'dewptf' in query_components:
            data_array['Dew_point_[C]'] = round((float(val)-32) * 5/9,1) if val is not None else None
            
        # windchillf
        val = get_valid_val('windchillf')
        if 'windchillf' in query_components:
            data_array['Wind_chill_[C]'] = round((float(val)-32) * 5/9,1) if val is not None else None
            
        # absbaromin
        val = get_valid_val('absbaromin')
        if 'absbaromin' in query_components:
            data_array['Abs_Barometric_pressure_[hpa]'] = round((float(val)*33.86389),1) if val is not None else None
            
        # baromin
        val = get_valid_val('baromin')
        if 'baromin' in query_components:
            data_array['Barometric_pressure_[hpa]'] = round((float(val)*33.86389),2) if val is not None else None
            
        # windspeedmph
        val = get_valid_val('windspeedmph')
        if 'windspeedmph' in query_components:
            data_array['Wind_speed_[m/s]'] = round((float(val)*0.44704),2) if val is not None else None
            
        # windgustmph
        val = get_valid_val('windgustmph')
        if 'windgustmph' in query_components:
            data_array['Wind_gust_speed_[m/s]'] = round((float(val)*0.44704),2) if val is not None else None
            
        # winddir
        val = get_valid_val('winddir')
        if 'winddir' in query_components:
            data_array['Wind_direction_[degree]'] = int(val) if val is not None else None
            
        # rainin
        val = get_valid_val('rainin')
        if 'rainin' in query_components:
            data_array['Rain_rate_[mm/h]'] = round((float(val)*25.4),2) if val is not None else None
            
        # dailyrainin
        val = get_valid_val('dailyrainin')
        if 'dailyrainin' in query_components:
            data_array['Rain_daily_[mm/d]'] = round((float(val)*25.4),2) if val is not None else None
            
        # weeklyrainin
        val = get_valid_val('weeklyrainin')
        if 'weeklyrainin' in query_components:
            data_array['Rain_weekly_[mm/w]'] = round((float(val)*25.4),2) if val is not None else None
            
        # monthlyrainin
        val = get_valid_val('monthlyrainin')
        if 'monthlyrainin' in query_components:
            data_array['Rain_monthly_[mm/m]'] = round((float(val)*25.4),2) if val is not None else None
            
        # solarradiation
        val = get_valid_val('solarradiation')
        if 'solarradiation' in query_components:
            data_array['Solar_radiation_[W/m^2]'] = float(val) if val is not None else None
            
        # UV
        val = get_valid_val('UV')
        if 'UV' in query_components:
            data_array['UV_[index]'] = float(val) if val is not None else None
            
        # indoortempf
        val = get_valid_val('indoortempf')
        if 'indoortempf' in query_components:
            data_array['Temperature_in_[C]'] = round((float(val)-32) * 5/9,1) if val is not None else None
            
        # indoorhumidity
        val = get_valid_val('indoorhumidity')
        if 'indoorhumidity' in query_components:
            data_array['Humidity_in_[%]'] = int(val) if val is not None else None
            
        # lowbatt
        val = get_valid_val('lowbatt')
        if 'lowbatt' in query_components:
            data_array['Low_battery_[]'] = (100 if int(val) == 0 else 0) if val is not None else None
        else:
            data_array['Low_battery_[]'] = 100
            
        return data_array

    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        parsed_data = MyHttpRequestHandler.parse_wu_data(query_components)
        
        http_message = str(parsed_data).replace("'", '"')
        html = f"<html><head></head><body><h1>{http_message}</h1></body></html>"
        response_bytes = bytes(html, "utf8")
        
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Connection", "close")
        self.end_headers()
        
        # Send the response to the weather station immediately to prevent timeouts and retries
        self.wfile.write(response_bytes)
        self.wfile.flush()
        
        # Get current timestamp in ISO format with timezone
        current_time = datetime.now().astimezone().isoformat()
        publish(client, f"{MQTT_TOPIC}/last_update", current_time)
        
        # Publish all available data
        data_mapping = {
            'Temperature_out_[C]': 'temperature_out',
            'Humidity_out_[%]': 'humidity_out',
            'Dew_point_[C]': 'dewpoint',
            'Wind_direction_[degree]': 'wind_direction',
            'Wind_speed_[m/s]': 'wind_speed',
            'Wind_gust_speed_[m/s]': 'wind_gust_speed',
            'Rain_rate_[mm/h]': 'rain_rate',
            'Rain_daily_[mm/d]': 'rain_daily',
            'Rain_weekly_[mm/w]': 'rain_weekly',
            'Rain_monthly_[mm/m]': 'rain_monthly',
            'Solar_radiation_[W/m^2]': 'solar_radiation',
            'UV_[index]': 'uv_index',
            'Temperature_in_[C]': 'temperature_in',
            'Humidity_in_[%]': 'humidity_in',
            'Barometric_pressure_[hpa]': 'barometric_pressure',
            'Abs_Barometric_pressure_[hpa]': 'abs_barometric_pressure',
            'Low_battery_[]': 'low_battery'
        }

        for data_key, topic_suffix in data_mapping.items():
            if data_key in parsed_data:
                val = parsed_data[data_key]
                if val is None:
                    # Publish offline to sensor availability
                    publish(client, f"{MQTT_TOPIC}/{topic_suffix}/availability", "offline", retain=True)
                else:
                    # Publish online to sensor availability AND the value to state topic
                    publish(client, f"{MQTT_TOPIC}/{topic_suffix}/availability", "online", retain=True)
                    publish(client, f"{MQTT_TOPIC}/{topic_suffix}", val)
        return

handler_object = MyHttpRequestHandler
my_server = socketserver.TCPServer(("", WEBSERVER_PORT), handler_object)
my_server.serve_forever()
