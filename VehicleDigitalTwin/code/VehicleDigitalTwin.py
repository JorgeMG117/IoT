import json
import threading
import requests
import time
from math import radians, cos, sin, acos
import time
import random
import os


google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY', "AIzaSyB97GoJWu-r3CLBiJ_7LWC-FG_odLdSPqU")

pending_routes = []

currentRouteDetailedSteps = []
vehicleControlCommands = []
current_command = {"SteeringAngle": 90.0, "Speed": 50.0, "Time": 5.0}

current_steering = 90.0
current_speed = 0.0
previous_speed = 0.0
current_position = {"latitude": 0.0, "longitude": 0.0}

current_leds = [{"Color": "White", "Intensity": 0.0, "Blinking": "False"}, {"Color": "White", "Intensity": 0.0, "Blinking": "False"}, {"Color": "Red", "Intensity": 0.0, "Blinking": "False"}, {"Color": "Red", "Intensity": 0.6, "Blinking": "False"}]
current_ldr = 6.0
current_obstacle_distance = 0.0

def generate_random(min, max):
    return random.uniform(min, max)

### ENVIRONMENT SIMULATOR ###

def light_simulator():
    global current_ldr, current_obstacle_distance
    if current_obstacle_distance > 0.0:
        current_ldr += generate_random(-300.0, 300.0)
    if current_ldr <= 0.0:
        current_ldr = generate_random(0.0, 3000.0)

def obstacle_simulator():
    global current_obstacle_distance
    if current_obstacle_distance > 0.0:
        current_obstacle_distance += generate_random(-5.0, 5.0)
    if current_obstacle_distance <= 0.0:
        current_obstacle_distance = generate_random(0.0, 50.0)

def simulate_environment():
    global current_command, current_speed, current_obstacle_distance, previous_speed

    light_simulator()
    obstacle_simulator()

    # frenar
    if current_obstacle_distance < 10:
        previous_speed = current_speed
        current_speed = 0
    else:
        previous_speed = current_speed
        current_speed = current_command["Speed"]
    
    time.sleep(60)



### LED CONTROLLER ###

def led_controller():
    global current_ldr, current_leds, current_steering, current_speed, previous_speed

    while True:
        # desactivar iluminacion de posicion
        # luces delanteras
        current_leds[0]["Intensity"] = 0.0
        current_leds[0]["Blinking"] = "False"
        current_leds[0]["Color"] = "White"

        current_leds[1]["Intensity"] = 0.0
        current_leds[1]["Blinking"] = "False"
        current_leds[1]["Color"] = "White"

        # luces traseras
        current_leds[2]["Intensity"] = 0.0
        current_leds[2]["Blinking"] = "False"
        current_leds[2]["Color"] = "Red"

        current_leds[3]["Intensity"] = 0.0
        current_leds[3]["Blinking"] = "False"
        current_leds[3]["Color"] = "Red"

        # iluminacion de posicion
        if current_ldr < 1000:
            # luces delanteras
            current_leds[0]["Intensity"] = 100.0
            current_leds[0]["Blinking"] = "False"
            current_leds[0]["Color"] = "White"

            current_leds[1]["Intensity"] = 100.0
            current_leds[1]["Blinking"] = "False"
            current_leds[1]["Color"] = "White"

            # luces traseras
            current_leds[2]["Intensity"] = 50.0
            current_leds[2]["Blinking"] = "False"
            current_leds[2]["Color"] = "Red"

            current_leds[3]["Intensity"] = 50.0
            current_leds[3]["Blinking"] = "False"
            current_leds[3]["Color"] = "Red"
            

        # iluminacion de intermitencia
        if current_steering > 100: #izquierda
            # luces delanteras
            current_leds[0]["Intensity"] = 100.0
            current_leds[0]["Blinking"] = "True"
            current_leds[0]["Color"] = "Yellow"
            
            # luces trasera izq
            current_leds[2]["Intensity"] = 100.0
            current_leds[2]["Blinking"] = "False"
            current_leds[2]["Color"] = "White"
        elif current_steering < 80: #derecha
            # luces delanteras
            current_leds[1]["Intensity"] = 100.0
            current_leds[1]["Blinking"] = "True"
            current_leds[1]["Color"] = "Yellow"
            
            # luces trasera der
            current_leds[3]["Intensity"] = 100.0
            current_leds[3]["Blinking"] = "False"
            current_leds[3]["Color"] = "White"
        

        # iluminacion de frenado
        if current_speed < previous_speed:
            # luces traseras
            current_leds[2]["Intensity"] = min(current_leds[2]["Intensity"] + 50.0, 100.0)
            current_leds[2]["Blinking"] = "False"
            current_leds[2]["Color"] = "Red"

            current_leds[3]["Intensity"] = min(current_leds[3]["Intensity"] + 50.0, 100.0)
            current_leds[3]["Blinking"] = "False"
            current_leds[3]["Color"] = "Red"

        
    


### ROUTES ###

def decode_polyline(polyline_str):
    """Pass a Google Maps encoded polyline string; returns list of lat/lon pairs"""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}
    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0
            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            if (result & 1):
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)
        lat += changes['latitude']
        lng += changes['longitude']
        coordinates.append((lat / 100000.0, lng / 100000.0))
    return coordinates


def get_detailed_steps(steps):
    """
    
    {'distance': {'text': '0.8 km', 'value': 805}, 'duration': {'text': '1 min', 'value': 67}, 'end_location': {'lat': 45.49558769999999, 'lng': -73.5671321}, 'html_instructions': 'Take exit <b>4</b> toward <b>Rue de la Montagne N</b>/<wbr/><b>Rue Saint-Jacques</b>', 'maneuver': 'ramp-right', 'polyline': {'points': '{}stGn`a`MAQAAKOaAyAgCqDaAuAWc@IOCCWe@We@IQs@yAWo@AEQk@Ka@[qAGUs@sBSs@AAYeAe@mBMk@AAMk@AAOk@Ok@K[GKAASUSOICOISE[@QAO?IAGC'}, 'start_location': {'lat': 45.4910163, 'lng': -73.5746435}, 'travel_mode': 'DRIVING'}"""

    detailed_steps = []
    for step in steps:
        stepSpeed = (step["distance"]["value"] / 1000) / (step["duration"]["value"] / 3600)
        stepDistance = step["distance"]["value"]
        stepTime = step["duration"]["value"]

        try:
            stepManeuver = step["maneuver"]
        except:
            stepManeuver = "Straight"

        substeps = decode_polyline(step["polyline"]["points"])


      
        for index in range(len(substeps) - 1):
                p1 = {"latitude": substeps[index][0], "longitude": substeps[index][1]}
                p2 = {"latitude": substeps[index + 1][0], "longitude": substeps[index + 1][1]}

                points_distance = distance(p1, p2)
                if points_distance > 0.001:
                    subStepDuration = stepDistance / stepSpeed
                    new_detailed_step = {"Origin": p1, "Destination": p2, "Speed": stepSpeed, "Time": subStepDuration, "Distance": points_distance, "Maneuver": stepManeuver}

                    detailed_steps.append(new_detailed_step)

    #print(detailed_steps[0])
    return detailed_steps



def get_commands(currentRouteDetailedSteps):
    #{"SteeringAngle": 90.0, "Speed": 50.0, "Time": 5.0}
    global vehicleControlCommands
    index = 0
    for detailed_step in currentRouteDetailedSteps:
        index += 1
        #print(f"Generando el comando {index} para el paso {detailed_step}")
        maneuver = detailed_step["Maneuver"].upper()
        if maneuver in ["STRAIGHT", "RAMP_LEFT", "RAMP_RIGHT", "MANEUVER_UNSPECIFIED"]:
            steering_angle = 90.0
        elif maneuver == "TURN_LEFT":
            steering_angle = 45.0
        elif maneuver == "UTURN_LEFT":
            steering_angle = 0.0
        elif maneuver == "TURN_SHARP_LEFT":
            steering_angle = 15.0
        elif maneuver == "TURN_SLIGHT_LEFT":
            steering_angle = 60.0
        elif maneuver == "TURN_RIGHT":
            steering_angle = 135.0
        elif maneuver == "UTURN_RIGHT":
            steering_angle = 180.0
        elif maneuver == "TURN_SHARP_RIGHT":
            steering_angle = 105.0
        elif maneuver == "TURN_SLIGHT_RIGHT":
            steering_angle = 150.0
        new_command = {"SteeringAngle": steering_angle, "Speed": detailed_step["Speed"], "Time": detailed_step["Time"]}
        vehicleControlCommands.append(new_command)
    #print(vehicleControlCommands[0])

def routes_manager(origin_address="Toronto", destination_address="Montreal"):
    global currentRouteDetailedSteps
    global vehicleControlCommands
    print("Asignando una ruta al vehículo")
    url = "https://maps.googleapis.com/maps/api/directions/json?origin=" + origin_address + "&destination=" + destination_address + "&key=" + google_maps_api_key
    print("URL: {}".format(url))
    payload = {}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    current_route = response.text
    # print("La ruta es: {}".format(response.text))
    steps = response.json()["routes"][0]["legs"][0]["steps"]
    # print(steps)
    # print(steps)
    currentRouteDetailedSteps = get_detailed_steps(steps)
    get_commands(currentRouteDetailedSteps)
    # print("He acabado de asignar los comandos al vehículo")




def execute_command(command, step):
    global current_steering, current_speed, current_position, previous_speed
    current_steering = command["SteeringAngle"]
    previous_speed = current_speed
    current_speed = command["Speed"]
    time.sleep(command["Time"])
    current_position = step["Destination"]




def distance(p1, p2):
    p1Latitude = p1["latitude"]
    p1Longitude = p1["longitude"]
    p2Latitude = p2["latitude"]
    p2Longitude = p2["longitude"]
    earth_radius = {"km": 6371.0087714, "mile": 3959}
    result = earth_radius["km"] * acos(
        cos(radians(p1Latitude)) * cos(radians(p2Latitude)) *
        cos(radians(p2Longitude) - radians(p1Longitude)) +
        sin(radians(p1Latitude)) * sin(radians(p2Latitude))
    )
    return result

### MAIN ###
    
def vehicle_controller():
    global pending_routes, current_command
    while True:
        if pending_routes != []:
            route = pending_routes.pop(0)
            origin = route["Origin"]
            destination = route["Destination"]

            routes_manager(origin, destination)

            global vehicleControlCommands, currentRouteDetailedSteps

            print(len(vehicleControlCommands))
            print(len(currentRouteDetailedSteps))

            for index in range(len(vehicleControlCommands)):
                print("Ejecutando comando " + str(vehicleControlCommands[index]))
                print(index)
                current_command = vehicleControlCommands[index]
                execute_command(current_command, currentRouteDetailedSteps[index])
                #del vehicleControlCommands[0]

            vehicleControlCommands = []
            currentRouteDetailedSteps = []

            #break
        else:
            print("No hay rutas pendientes")
            time.sleep(10)

def routes_loader(route_json):
    """Añade una nueva ruta a la lista de rutas pendientes a partir de un JSON."""
    # Parse the JSON string into a Python dictionary
    route = json.loads(route_json)
    origin = route["Origin"]
    destination = route["Destination"]

    # Append the route dictionary to the global pending routes list
    global pending_routes
    pending_routes.append(route)
    print(f"Ruta agregada: De {origin} a {destination}")

def vehicle_stop():
    global vehicleControlCommands, currentRouteDetailedSteps, current_steering, current_speed, current_leds, current_ldr, current_obstacle_distance, previous_speed
    vehicleControlCommands = []
    currentRouteDetailedSteps = []
    current_steering = 90.0
    previous_speed = current_speed
    current_speed = 0
    current_leds_str = '[{"Color": "White", "Intensity": 0.0, "Blinking": "False"}, {"Color": "White", "Intensity": 0.0, "Blinking": "False"}, {"Color": "Red", "Intensity": 0.0, "Blinking": "False"}, {"Color": "Red", "Intensity": 0.6, "Blinking": "False"}]'
    current_leds = json.loads(current_leds_str)
    current_ldr = 6.0
    current_obstacle_distance = 0.0



if __name__ == '__main__':
    try:
        my_route = '{"Origin": "Toronto", "Destination": "Montreal"}'
        routes_loader(my_route)

        t2 = threading.Thread(target=simulate_environment, daemon=True)
        t2.start()

        t3 = threading.Thread(target=vehicle_controller, daemon=True)
        t3.start()
        t4 = threading.Thread(target=led_controller, daemon=True)
        t4.start()
        t2.join()
        t3.join()
        t4.join()

    except Exception as e:
        print(e)
        vehicle_stop()
