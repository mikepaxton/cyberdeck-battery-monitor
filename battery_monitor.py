"""
Author: Mike Paxton
Creation Date: 08/18/24
Python Version: 3

Overview:---------------------------------------------------------------------------------------
This is designed to work with Waveshares UPS S3 and their UPS HAT (C) and the Raspberry Pi

The overall purpose of this code is to continuously check the Pi's UPS battery level and warn you
via org.freedesktop.Notifications notify-send if the battery has dropped below a specific percentage (battery_is_low)
and execute a system shutdown if the battery drops below a second specific percentage (battery_shutdown).

How the code executes:
Every x number seconds (battery_check_interval) the code will check the percentage of battery life
remaining of the UPS.  If the percentage drops below the battery_is_low variable then a battery low
warning is displayed onscreen using the Linux Notification System (notify-send).
This notification is meant to alert the user that the UPS battery is getting low.

If the percentage drops below the battery_shutdown variable then another message is displayed
onscreen notifying the user that the system will shutdown in 10 seconds unless plugged into power.
If the user does not plug into power, the code will check one final time to make sure the UPS
has not been plugged into power.  If it has not, then a "shutdown -h now"" is run.
If power was re-established then the system will abort out of the shutdown and continue to monitor
the UPS.

Both UPS's use the i2c bus.  The UPS S3 uses address 0x41, while the HAT uses 0x43 by default.
Change the appropriate two lines below to reflect the correct i2c address of your UPS.

This software is meant to be run automatically on boot by using either cron or /etc/rc.local
Use the following for both: /usr/bin/python3 /path/to/your/script.py &
For cron use:
sudo crontab -e
@reboot /usr/bin/python3 /path/to/your/script.py



------------------------------------------------------------------------------------------------
"""

import time
import board
from adafruit_ina219 import ADCResolution, BusVoltageRange, INA219
import subprocess

# User variables
battery_is_low = 25.00 # Initial Notification Warning
battery_shutdown = 10.00 # Battery is criticaly low, will shutdown unless power is plugged in.
battery_check_interval = 10 # In seconds
i2c_address=0x43 # UPS i2c address
debug = False


i2c_bus = board.I2C()  # uses board.SCL and board.SDA

#ina219 = INA219(i2c_bus, 0x41) # Used for Pi UPS S3
ina219 = INA219(i2c_bus, i2c_address) # Used for Pi UPS HAT (c)

if debug == True:
    print("ina219 test")
    # display some of the advanced field (just to test)
    print("Config register:")
    print("  bus_voltage_range:    0x%1X" % ina219.bus_voltage_range)
    print("  gain:                 0x%1X" % ina219.gain)
    print("  bus_adc_resolution:   0x%1X" % ina219.bus_adc_resolution)
    print("  shunt_adc_resolution: 0x%1X" % ina219.shunt_adc_resolution)
    print("  mode:                 0x%1X" % ina219.mode)
    print("")

# optional : change configuration to use 32 samples averaging for both bus voltage and shunt voltage
ina219.bus_adc_resolution = ADCResolution.ADCRES_12BIT_32S
ina219.shunt_adc_resolution = ADCResolution.ADCRES_12BIT_32S
# optional : change voltage range to 16V
ina219.bus_voltage_range = BusVoltageRange.RANGE_16V

# Returns the remaining battery life of the UPS
# Change the return depending on the UPS you are using.
def get_battery_percentage(bus_voltage):
    #return ((bus_voltage - 9.0) / (12.6 - 9.0)) * 100 # Use for Pi5 WaveShare UPS S3
    return ((bus_voltage - 3.0) / (4.1 - 3.0)) * 100 # Use for Pi Zero WaveShare UPS HAT (C)

# Use notify-send to send a desktop notification
def send_alert(message):
    subprocess.run(['notify-send', '-i', '/home/admin/.local/share/icons/candy-icons/status/scalable/battery-030.svg','-t','2000','Battery Alert', message])

# Use notify-send to send desktop notification. Critical messages will not disappear.
def send_critical_alert(message):
    subprocess.run(['notify-send','--urgency=critical', '-i', '/home/admin/.local/share/icons/candy-icons/status/scalable/battery-020.svg','Battery Critical', message])

# Execute system shutdown
def shutdown_system():
    subprocess.run(['sudo', 'shutdown', '-h', 'now'])

def battery_low():
    # 10-second countdown at a 3 second notificaton interval
    for i in range(10, 0, -3):
        print(f"Shutting down in {i} seconds...")
        send_alert(f"Shutting down in {i} seconds...")
        # TODO: Probably need to insert a battery check here to make sure user hasn't plugge into power.
        time.sleep(3)

# If the battery has dropped below the battery_shutdown level
# Initiate a shutdown of the computer.
# Pause for 5 seconds so the user can read the message.
def system_shutdown():
    print("System is shutting down!")
    time.sleep(5) # Pause for a moment in case user has plugged into power, let ina219 balance out.
    subprocess.run(['sudo', 'shutdown', '-h', 'now'])

# measure and display loop
while True:
    bus_voltage = ina219.bus_voltage  # voltage on V- (load side)
    shunt_voltage = ina219.shunt_voltage  # voltage between V+ and V- across the shunt
    current = ina219.current  # current in mAa
    power = ina219.power  # power in watts
    #percent = ((bus_voltage - 9.0) / (12.6 - 9.0)) * 100 # Use with UPS S3
    percent = (bus_voltage - 3.0) / (4.1 - 3.0)*100 # Use with the Pi Zero's UPS HAT (C)
    if(percent > 98):percent = 100
    if(percent < 0):percent = 0

    # INA219 measure bus voltage on the load side. So PSU voltage = bus_voltage + shunt_voltage
    print("Voltage (VIN+) : {:6.3f}   V".format(bus_voltage + shunt_voltage))
    print("Voltage (VIN-) : {:6.3f}   V".format(bus_voltage))
    print("Shunt Voltage  : {:8.5f} V".format(shunt_voltage))
    print("Shunt Current  : {:7.4f}  A".format(current / 1000))
    print("Power Calc.    : {:8.5f} W".format(bus_voltage * (current / 1000)))
    print("Power Register : {:6.3f}   W".format(power))
    print("Percent        : {:6.2f}%".format(percent))
    print("")

    # Check internal calculations haven't overflowed (doesn't detect ADC overflows)
    if ina219.overflow:
        print("Internal Math Overflow Detected!")
        print("")

    # Run the get_battery_percentage function
    battery_percentage = get_battery_percentage(bus_voltage)

    # Used to determine if power has been restored to the UPS.
    # A negative voltage means power has not been restored, we are still running off of UPS.
    get_power_calc = bus_voltage * (current / 1000)

    if get_power_calc <= -5.00:
        print("No input voltage detected")
        send_alert(f"We are running on the Pi5's UPS battery: {battery_percentage:.2f}% left on battery")

    # Send alert if battery percentage is below "battery_is_low user variable
    if battery_percentage <= battery_is_low:
        print("Ran Battery Percentage")
        send_alert(f"Pi5 UPS Battery Low: {battery_percentage:.2f}% Remaining! Charge ASAP!")

    # Send alert that battery has dropped below battery_shutdown user variable and will shutdown unless plugged into power source.
    # If low battery alert was sent, system is in 10 sec. countdown.  Check one final time to see if user
    # plugged in power.  If yes, then go back to standard status checking.
    # If no, then initiate a system shutdown.
    if battery_percentage <= float(battery_shutdown):
        send_critical_alert(f"Battery critically low: {battery_percentage:.2f}% remaining! Plug into power or system will shutdown in 10 seconds.")
        battery_low()
        if battery_percentage <=battery_shutdown and get_power_calc <=-1.00: # check to see if power has power been re-established?
            send_critical_alert(f"Battery is critical: {battery_percentage:.2f}% System is Shutting down...")
            #system_shutdown()
            break
        else:
            send_alert(f"Battery is charging: {battery_percentage:.2f}%")

    time.sleep(battery_check_interval)
