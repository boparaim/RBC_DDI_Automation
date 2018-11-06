# /**
#  * @author Manvinder Boparai
#  * @version 01 Nov 2018
#  * @filename main.py
#  *
#  * Validates the user input and stores it in the second table.
#  *
#  * Copyright 2018 Empowered Networks Inc.
#  */

import datetime
import io
import json
import sys
import threading
import time
import traceback
from collections import namedtuple

import mysql.connector
import yaml


# utility function to print a log message
def log(tag, msg):
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")+' - ['+tag.upper()+'] >> '+msg)


log('start', 'com_rbc_automation_ddi/main.py')

# read properties file
settings = yaml.safe_load(io.open('properties.yaml', 'r', encoding='utf-8'))
#print(yaml.dump(settings), settings)

# global object, used to store the de-duplicated operations
# into the db
finalJson = {}

# connection to the db
connection = None

# tuple to store table attributes
Recipe = namedtuple("Recipe", "key host startTime endTime")


# add given operation to the final_json object
def add_to_final_json(recipe, operation):
    if recipe.host not in finalJson:
        finalJson[recipe.host] = {}
    if str(recipe.startTime) not in finalJson[recipe.host]:
        finalJson[recipe.host][str(recipe.startTime)] = []
    operation['key'] = recipe.key + '_' + 'start'
    finalJson[recipe.host][str(recipe.startTime)].append(operation)

    if recipe.endTime is not None:
        if str(recipe.endTime) not in finalJson[recipe.host]:
            finalJson[recipe.host][str(recipe.endTime)] = []
        operation = operation.copy()
        operation['key'] = recipe.key + '_' + 'end'
        finalJson[recipe.host][str(recipe.endTime)].append(operation)


# parse operations for valid arguments
def parse_operations(operations, recipe):
    for operation in operations:
        if 'name' not in operation:
            log('operation', 'name not defined for this operation')
            continue
        if 'current' not in operation:
            log('operation', 'current value not defined for this operation')
            continue
        if 'requested' not in operation:
            log('operation', 'requested value not defined for this operation')
            continue

        if operation['name'] == 'ipv4Change':
            log('operation', 'adding ipv4Change for ' + recipe.host)
            add_to_final_json(recipe, operation)
        elif operation['name'] == 'ipv6Change':
            log('operation', 'adding ipv6Change for ' + recipe.host)
            add_to_final_json(recipe, operation)
        elif operation['name'] == 'dnsChange':
            log('operation', 'adding dnsChange for ' + recipe.host)
            add_to_final_json(recipe, operation)
        else:
            log('operation', 'unsupported operation' + operation)


# get ddi requests from db and process them
def get_requests():
    global connection
    cursor = connection.cursor()

    get_requests_query = ("SELECT *"
                          " FROM `{}`"
                          " WHERE action REGEXP '[aA][dD][dD]'"
                          " ORDER BY id").format(settings['main']['source_table'])

    cursor.execute(get_requests_query, ())

    # get valid ddi requests that we nee to process
    # ignore removed and canceled requests
    # requests with invalid operations
    # requests with invalid star or end timestamps
    # requests with undefined target host
    for (id, host, start_time, end_time, type, action, operations) in cursor:
        log('ddi_change_request', '{}: {} - start = {}, end = {}, type = {}, action = {}, operations = {}'
                .format(id, host, start_time, end_time, type, action, operations))

        if action == 'cancel':
            log('canceled_request', 'ignoring ddi_change_request | id: {}.'.format(id))
            continue

        if action == 'remove':
            log('removed_request', 'ignoring ddi_change_request | id: {}.'.format(id))
            continue

        try:
            operations_json = json.loads(operations)
        except:
            print('json_error', sys.exc_info()[0])
            traceback.print_exc(file=sys.stdout)
            continue
        finally:
            pass

        if not isinstance(operations_json, list):
            log('operations', 'operations need to be JSON arrays | id: {}.'.format(id))
            continue

        if type == 'one-time':
            now_time = datetime.datetime.now()
            if now_time > datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S'):
                log('time', 'start time has passed | id: {}.'.format(id))
                continue

            if (end_time is not None) and (now_time > datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')):
                log('time', 'end time has passed | id: {}.'.format(id))
                continue

        if host is None or host == '':
            log('host', 'no target host defined | id: {}.'.format(id))
            continue

        if type == 'one-time':
            if action == 'add':
                recipe = Recipe(key='add_one-time', host=host, startTime=start_time, endTime=end_time)
                parse_operations(operations_json, recipe)

            else:
                log('request_action', 'unsupported action ' + action)

        elif type == 're-occurring':
            if action == 'add':
                recipe = Recipe(key='add_re-occurring', host=host, startTime=start_time, endTime=end_time)
                parse_operations(operations_json, recipe)

            else:
                log('request_action', 'unsupported action ' + action)

        else:
                log('request_type', 'unsupported type ' + type)

    cursor.close()


# store valid ddi requests in the db
def store_requests():
    global connection
    global finalJson
    final_json_string = json.dumps(finalJson)
    #print(finalJson, final_json_string)

    cursor = connection.cursor()
    cursor.execute("TRUNCATE TABLE `{}`".format(settings['main']['dest_table']), ())
    connection.commit()
    cursor.close()

    cursor = connection.cursor()

    cron_operation_insert = ("INSERT INTO `{}`"
                             " (host, time, operation, current, requested) "
                             " VALUES (%s, %s, %s, %s, %s)").format(settings['main']['dest_table'])

    for host in finalJson:
        for thisTime in finalJson[host]:
            for operation in finalJson[host][thisTime]:
                data = (host, thisTime,
                        operation['key'] + '_' + operation['name'],
                        operation['current'],
                        operation['requested'])
                log('store_request', str(data))
                cursor.execute(cron_operation_insert, data)

    connection.commit()

    cursor.close()

    finalJson = {}


# representing a db-poll cycle
class Cycle(threading.Thread):
    def __init__(self, interval):
        threading.Thread.__init__(self)
        self.interval = interval

    def run(self):
        log('poll_cycle', 'starting db polling')
        while True:
            print("-----------------------------------------")
            log('sync', 'start')
            global connection
            connection = mysql.connector.connect(
                user=settings['database']['username'],
                password=settings['database']['password'],
                host=settings['database']['host'],
                port=settings['database']['port'],
                database=settings['main']['source_schema'])
            get_requests()
            store_requests()
            connection.close()
            log('sync', 'end')
            print("-----------------------------------------\n")

            time.sleep(60 * self.interval)


# start the infinite loop
syncCycle = Cycle(settings['main']['interval'])
syncCycle.start()















# make sure system time is correct
# make sure cron is installed and functioning properly

# might need to put selinux in permissive mode for cron to work
# setenforce 0

# /etc/cron*
# /var/spool/cron*
# /var/log/cron

# required python packages
# PyYAML	3.13	3.13
# mysql-connector-python	8.0.12	8.0.13
#
# pip	10.0.1	18.1
# protobuf	3.6.1	3.6.1
# setuptools	39.1.0	40.4.3
# six	1.11.0	1.11.0


# sudo python main.py >> logs/main.log &