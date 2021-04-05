import telnetlib
import json
import csv
import os
import configparser
import colorama
import re
import threading

try:
    import plotly.express as px
except:
    print("plotly not found to install: pip3 install plotly")
    exit(-1)
try:
    import pandas as pd
except:
    print("plotly not found to install: pip3 install pandas")
    exit(-1)

from plotly import offline
from datetime import datetime
from time import sleep
from sys import platform, version_info

from hourly_average_NODAYS_class import HourlyPlot

#Initial check to see if they are running 3.6 or greater
version_major = version_info.major
version_minor = version_info.minor

if version_major < 3 or (version_major == 3 and version_minor < 6):
    print('This program requires Python 3.6 and above, please consider upgrading')

#Initializes colorama to use text colors!
colorama.init()

#Change this to where you stored your files for Windows to find them correctly
if platform == 'win32':
    os.chdir('C:/python/humidity')

config = configparser.ConfigParser()
try:
    os.path.getsize('config.ini')
except OSError:
    config['LOGIN'] = {
                    'HOST': '192.168.168.168',
                    'USERNAME': 'super',
                    'PASSWORD': 'super',
                    }
    config['OTHER'] = {
                    'cszPort': 'U1',
                    'filename': 'humidity',
                    'logging': 1,
                    }
    config['EXPERIMENTAL'] = {
                    'DEBUG': 'False',
                    }

    with open('config.ini', 'w') as f:
        config.write(f)
else:
    config.read('config.ini')

# User changeable settings
HOST = config['LOGIN']['HOST']
USERNAME = config['LOGIN']['USERNAME']
PASSWORD = config['LOGIN']['PASSWORD']
cszPort = config['OTHER']['cszPort']
FILENAME = config['OTHER']['filename']
LOGGING = config['OTHER']['logging']
DEBUG = config['EXPERIMENTAL']['DEBUG']

# Convert strings into bool
if DEBUG == 'True':
    DEBUG = True
elif DEBUG == 'False':
    DEBUG = False

# Import debug stuff
if DEBUG:
    from random import randint

# append .csv at the end of the filename if its not there
if FILENAME.find('.csv') == -1:
    FILENAME += '.csv'

# Do not change
cszUnitResponse = "REM> "
is_running = None
event_log = []
thread_control = 0

def escape_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)

def add_event(message, type):
    """Adds a message to the event log"""
    # Severity of type:
    # 0 = Normal
    # 1 = Warning
    # 2 = Severe
    global event_log

    try:
        os.path.getsize('eventlog.csv')
    except OSError:
        with open('eventlog.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['MESSAGE', 'SEVERITY'])

    if len(event_log) > 50:
        del event_log[:45]
    event_log.append(message)

    message = escape_ansi(message)

    eventTemp = [
        f'"{message}"',
        f'"{type}"',
                ]
    with open('eventlog.csv', 'a', newline='') as file:
        writer = csv.writer(file, quotechar="'")
        writer.writerow(eventTemp)

    return None

def connect_TelNet():
    """Tries to connect to the specified telnet server. Returns None if cannot connect"""
    try:
        tn = telnetlib.Telnet(HOST, timeout=5)
    except Exception:
        return None
    else:
        return tn

def login_TelNet(client_connection):
    """Tries to log into the specified telnet server. Returns None if cannot connect"""
    client_connection.read_until(b"login: ")
    client_connection.write(USERNAME.encode('ascii') + b"\n")

    # password screen
    if PASSWORD:
        client_connection.read_until(b"Password: ")
        client_connection.write(PASSWORD.encode('ascii') + b"\n")

    response = client_connection.read_until(cszUnitResponse.encode(), timeout=5).decode('ascii')
    if cszUnitResponse not in response:
        return None
    else:
        return response

def port_TelNet(client_connection):
    """Tries to connect to the specified port on the telnet server. Returns None if cannot connect / port is busy"""
    client_connection.write(b"/c "+cszPort.encode('ascii') + b"\r\n")

    response = client_connection.read_until(b"\n", timeout=5).decode('ascii')
    if "Busy." in response:
        return None

    response = client_connection.read_until(b"\n", timeout=5).decode('ascii')
    if response.find('Connected ') != -1:
        return response
    else:
        return None

def threaded_listener(connection):
    """Listens to the port... Multithreaded style!"""
    print('Starting thread...', end=" ")
    global is_running
    print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')

    iteration = 0
    print('Listening for data...', end=" ")

    if DEBUG:
        print(f'\n{colorama.Fore.YELLOW}DEBUG ENABLED, SKIPPING COLLECTION{colorama.Fore.RESET}')
        return None

    print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
    cszTemp = ""
    while thread_control == 1:
        is_running = True
        try:
            cszTemp = cszTemp + connection.read_until(b"}", timeout=1).decode('ascii')
            if (cszTemp.find("}") == -1):
                continue
            current_time = datetime.now().strftime("%m/%d/%y %H:%M:%S")
        except EOFError:
            add_event(f'Exception at {colorama.Fore.YELLOW}{current_time}{colorama.Fore.RESET}', 1)

        # Insert the csv header
        if iteration == 0:
            try:
                os.path.getsize(FILENAME)
            except OSError:
                with open(FILENAME, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(
                        [
                            "TIME",
                            "TEMP",
                            "TEMPFORMAT",
                            "PRESSURE",
                            "PRESSUREFORMAT",
                            "HUMIDITY",
                            "MODULE",
                        ]
                    )

        try:
            parsed_json = json.loads(cszTemp)
        except Exception:
            add_event(f'Exception at {colorama.Fore.YELLOW}{current_time}{colorama.Fore.RESET}', 1)
        else:
            cszModule = parsed_json["module"]
            fTemperature = float(parsed_json["temperature"])
            cszTemperatureFormat = parsed_json["format"]
            fPressure = float(parsed_json["pressure"])
            cszTPressureFormat = parsed_json["pressureformat"]
            fHumidity = float(parsed_json["humidity"])

            cszTemp = [
                f'"{current_time}"',
                f'"{fTemperature}"',
                f'"{cszTemperatureFormat}"',
                f'"{fPressure}"',
                f'"{cszTPressureFormat}"',
                f'"{fHumidity}"',
                f'"{cszModule}"',
                ]
            with open(FILENAME, 'a', newline='') as file:
                writer = csv.writer(file, quotechar="'")
                writer.writerow(cszTemp)
        
            if int(LOGGING) == 1:
                add_event(f"[RUN: {iteration}] [TEMP: {fTemperature}{cszTemperatureFormat}] [HUM: {fHumidity}%] [PRES: {fPressure}{cszTPressureFormat}] [TIME: {current_time}]", 0)
        
        iteration += 1
        cszTemp = ""

    add_event(f'Collection... {colorama.Fore.GREEN}ok{colorama.Fore.RESET}', 0)
    connection.write(b"\x18")

    try:
        connection.read_until(cszUnitResponse.encode()).decode('ascii')
    except EOFError:
        add_event(f'{colorama.Fore.YELLOW}Failed graceful disconnect{colorama.Fore.RESET}', 1)
        add_event(f'Collected data from port {cszPort} {colorama.Fore.BLUE}{iteration}{colorama.Fore.RESET} times', 0)
    else:
        add_event(f'{colorama.Fore.GREEN}Disconnected{colorama.Fore.RESET}', 0)
        add_event(f'Collected data from port {cszPort} {colorama.Fore.BLUE}{iteration}{colorama.Fore.RESET} times', 0)

    is_running = False

def establish_TelNet():
    """Connects, logs in, and checks port"""
    # Initial telnet connection
    print(f'Connecting to {HOST}...', end=" ")
    tn_connection = connect_TelNet()
    if tn_connection:
        print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
    else:
        print(f'{colorama.Fore.RED}failed{colorama.Fore.RESET}')
        if not DEBUG:
            exit(2)
        else:
            print(f'{colorama.Fore.YELLOW}DEBUG ENABLED, SKIPPING CONNECTION{colorama.Fore.RESET}')
    
    # Log in attempt to server
    print(f'Logging into {HOST} as {USERNAME}...', end=" ")
    tn_response = login_TelNet(tn_connection)
    if tn_response:
        print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
    else:
        print(f'{colorama.Fore.RED}failed{colorama.Fore.RESET}')
        if not DEBUG:
            exit(2)
        else:
            print(f'{colorama.Fore.YELLOW}DEBUG ENABLED, SKIPPING LOGIN{colorama.Fore.RESET}')

    # Connect to port
    print(f'Connecting to port {cszPort}...', end=" ")
    tn_response = port_TelNet(tn_connection)
    if tn_response:
        print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
    else:
        print(f'{colorama.Fore.RED}failed{colorama.Fore.RESET}')
        if not DEBUG:
            print(f'{colorama.Fore.RED}COULD NOT BIND TO PORT{colorama.Fore.RESET}')
            exit(2)
        else:
            print(f'{colorama.Fore.YELLOW}DEBUG ENABLED, SKIPPING PORT CONNECTION{colorama.Fore.RESET}')
    
    return tn_connection

def plot_graph(filename, plot_type):
    # Plot type: 0 = temp vs humidity, 1 = 24 hour averages
    print(f'Constructing plot from {filename}...', end=" ")
    df = pd.read_csv(filename)

    if df.empty:
        print(f'{colorama.Fore.RED}failed{colorama.Fore.RESET}')
        print(f'{colorama.Fore.RED}csv is empty! Gather some data to build plot!{colorama.Fore.RESET}')
        exit(2)
    
    plot_type = int(plot_type)
    # Gets rid of the .csv and appends .html to it
    plot_filename = FILENAME[:-4] + '.html'

    if plot_type == 0:

        fig = px.line(df, x = 'TIME', y = ['TEMP', 'HUMIDITY',],title='Time vs. Temperature vs. Humidity', template='plotly_dark')
        fig.update_xaxes(nticks= 24)
        fig.update_traces(mode="lines", hovertemplate=None)
        fig.update_layout(hovermode="x unified")
    elif plot_type == 1:

        hour_plot = HourlyPlot(filename)
        fig = hour_plot.build_plot()
    else:
        # spinner.fail(text='Unknown plot type')
        print(f'{colorama.Fore.RED}failed{colorama.Fore.RESET}')
        print(f'{colorama.Fore.RED}Unknown plot type{colorama.Fore.RESET}')
        return None

    print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')

    print('Displaying Plot...', end=" ")
    if platform == 'win32':
        offline.plot(fig, filename=plot_filename)
        print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
    elif platform == 'linux':
        offline.plot(fig, filename=plot_filename, auto_open=False)
        print(f'{colorama.Fore.RED}failed{colorama.Fore.RESET}')
        print(f'{colorama.Fore.RED}Linux based systems have trouble displaying the graph automatically. Please open {plot_filename} manually!{colorama.Fore.RESET}')
        sleep(4)
    else:
        offline.plot(fig, filename=plot_filename, auto_open=False)
        print(f'{colorama.Fore.RED}failed{colorama.Fore.RESET}')
        print(f'{colorama.Fore.RED}Unknown OS, please open {plot_filename} manually!{colorama.Fore.RESET}')
        sleep(4)

def option_one():
    '''Only listens for data'''
    global thread_control
    # establish telnet connect to target host
    tn_connection = establish_TelNet()
    
    thread_control = 1
    t1 = threading.Thread(target=threaded_listener, args=(tn_connection,))
    t1.start()
    sleep(1)
    print("Returning to main menu...")
    sleep(2)

def option_two(filename, plot_type):
    '''Only graphs the data'''
    # Construct a graph from the data
    plot_graph(filename, plot_type)

# User Interface

# Settings loop
def settings():
    # Get our globals
    global config, HOST, USERNAME, PASSWORD, cszPort, FILENAME

    while True:
        print(chr(27) + "[2J")
        print(f'Plot-o-Matic v2.0 Made with {colorama.Fore.RED}<3{colorama.Fore.RESET}', end=" ")
        print(f'\n1. Current Hostname: {HOST}\n2. Current Username: {USERNAME}\n3. Current Password: {PASSWORD}\n4. Port to Listen: {cszPort}\n5. Filename: {FILENAME}\n6. Back')
        user_input = input("Selection: ")
        if user_input == '1':
            user_input = input("Enter a new value for Hostname: ")
            config.set('LOGIN', 'HOST', user_input)
            HOST = user_input
            continue
        elif user_input == '2':
            user_input = input("Enter a new value for Username: ")
            config.set('LOGIN', 'USERNAME', user_input)
            USERNAME = user_input
            continue       
        elif user_input == '3':
            user_input = input("Enter a new value for Password: ")
            config.set('LOGIN', 'PASSWORD', user_input)
            PASSWORD = user_input
            continue
        elif user_input == '4':
            user_input = input("Enter a new value for cszPort: ")
            config.set('OTHER', 'cszPort', user_input)
            cszPort = user_input
            continue
        elif user_input == '5':
            user_input = input("Enter a new value for filename: ")
            
            if user_input.find('.csv') != -1:
                FILENAME = user_input
            else:
                FILENAME = user_input
                FILENAME += '.csv'
            config.set('OTHER', 'filename', user_input)
            continue
        elif user_input == '6':
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
            break

# Debug settings loop
def debug_settings():
    global config, is_running, LOGGING

    while True:
        print(chr(27) + "[2J")
        print(f'{colorama.Fore.YELLOW}Super Secret Debug Settings Menu!{colorama.Fore.RESET}\n')
        if is_running:
            print('1. Disable running status?')
        else:
            print('1. Enable running status?')

        print('2. Dump ini file contents')
        print('3. Generate spoofed event log')
        print('4. Flush event log')
        print('5. Event Log Settings')
        print('6. Exit')

        user_input = input('Selection: ')

        if user_input == '1':
            if is_running:
                is_running = False
            else:
                is_running = True
        elif user_input == '2':
            print(chr(27) + "[2J")
            print('to be done')
            input('Press Enter to continue...')
        elif user_input == '3':
            iteration = 0
            while True:
                random_number = randint(1, 3)

                if random_number == 1:
                    add_event('This is a standard event', 0)
                elif random_number == 2:
                    add_event(f'{colorama.Fore.YELLOW}This is a warning event{colorama.Fore.RESET}', 1)
                elif random_number == 3:
                    add_event(f'{colorama.Fore.RED}This is a severe event{colorama.Fore.RESET}', 2)

                iteration += 1

                if iteration == 10:
                    print('Filled event log!')
                    sleep(1)
                    break
        elif user_input == '4':
            print(f'{colorama.Fore.YELLOW}Flush! Down the drain!{colorama.Fore.RESET}')
            event_log.clear()
            sleep(1)
        elif user_input == '5':
            while True:
                print(chr(27) + "[2J")
                if int(LOGGING) == 1: 
                    print('Currently set to: Everything')
                elif int(LOGGING) == 2:
                    print('Currently set to: Only update messages')
                print('1. Log Everything')
                print('2. Log only errors')
                print('3. Exit')
                user_log = input('Selection: ')

                if user_log == '1':
                    config.set('OTHER', 'LOGGING', 1)
                    LOGGING = 1
                elif user_log == '2':
                    config.set('OTHER', 'LOGGING', 2)
                    LOGGING = 2
                elif user_log == '3':
                    break
                else:
                    print(f"{colorama.Fore.RED} Invalid selection, please try again")
                    sleep(1)
                    continue                    

        elif user_input == '6':
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
            break
        else:
            print(f"{colorama.Fore.RED} Invalid selection, please try again")
            sleep(1)
            continue

# Main loop
while True:
    print(chr(27) + "[2J")
    if not is_running:
        user_input = input(f"Status: {colorama.Fore.RED}Stopped{colorama.Fore.RESET}\nPlease Choose an Option:\n1. Only Listen\n2. Only Plot\n3. Listen and Plot\n4. Options\n5. Exit\nSelection: ")

        if user_input == '1':
            print(chr(27) + "[2J")
            option_one()
        elif user_input == '2':
            user_input = input(f"Please enter a csv file, include .csv. Leave blank for {FILENAME}: ")
            plot_input = input(f"Which plot would you like? 0 = Temp vs. Humid : 1 = Hourly Average: ")
            print(chr(27) + "[2J")
            if len(user_input) == 0:
                user_input = FILENAME

            option_two(user_input, plot_input)
        elif user_input == '3':
            user_input = input(f"Please enter a csv file, include .csv. Leave blank for {FILENAME}: ")
            plot_input = input(f"Which plot would you like? 0 = Temp vs. Humid : 1 = Hourly Average")
            print(chr(27) + "[2J")
            if len(user_input) == 0:
                user_input = FILENAME

            option_one()
            option_two(user_input, plot_input)
        elif user_input == '4':
            settings()
        elif user_input == '5':
            print('Thanks for using the Plot-o-Matic!')
            print('Stopping thread...', end=" ")
            thread_control = 0
            while is_running == True:
                sleep(1)
            print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
            colorama.deinit()
            break
        elif user_input == '99' and DEBUG == True:
            print(f"{colorama.Fore.YELLOW}DEBUG COMMAND ENTERED{colorama.Fore.RESET}")
            sleep(1)
            debug_settings()  
        else:
            print(f"{colorama.Fore.RED} Invalid selection, please try again{colorama.Fore.RESET}")
            sleep(1)
            continue
    else:
        user_input = input(f"Status: {colorama.Fore.GREEN}Running{colorama.Fore.RESET}\nPlease Choose an Option:\n1. Stop\n2. Plot\n3. Event Log\n4. Options\n5. Exit\nSelection: ")

        if user_input == '1':
            print('Stopping thread...', end=" ")
            thread_control = 0
            while is_running == True:
                continue
            print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
        elif user_input == '2':
            user_input = input(f"Please enter a csv file, include .csv. Leave blank for {FILENAME}: ")
            plot_input = input(f"Which plot would you like? 0 = Temp vs. Humid : 1 = Hourly Average: ")
            print(chr(27) + "[2J")
            if len(user_input) == 0:
                user_input = FILENAME

            option_two(user_input, plot_input)
        elif user_input == '3':
            print(chr(27) + "[2J")

            if len(event_log) == 0:
                print(f'{colorama.Fore.BLUE}Nothing to report!{colorama.Fore.RESET}')
            else:
                for item in event_log:
                    print(item)
            input('Press Enter to return...')
        elif user_input == '4':
            settings()
        elif user_input == '5':
            print('Thanks for using the Plot-o-Matic!')
            print('Stopping thread...', end=" ")
            thread_control = 0
            while is_running == True:
                continue
            print(f'{colorama.Fore.GREEN}ok{colorama.Fore.RESET}')
            colorama.deinit()
            break
        elif user_input == '99' and DEBUG == True:
            print(f"{colorama.Fore.YELLOW}DEBUG COMMAND ENTERED{colorama.Fore.RESET}")
            sleep(1)
            debug_settings()  
        else:
            print(f"{colorama.Fore.RED} Invalid selection, please try again{colorama.Fore.RESET}")
            sleep(1)
            continue
