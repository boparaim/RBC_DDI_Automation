import sys
import traceback
import datetime
import mysql.connector
import json
from collections import namedtuple
from subprocess import call
import subprocess
import threading
import time
import os

# make sure system time is correct
# make sure at and cron are installed and functioning properly

# sudo yum install at atd && atd
# check exists /var/run/atd.pid

finalJson = {}

def at():
    #os.chdir("/home/boparaim/")
    #call("pwd")
    #call(["ls", "-lah"])
    pass

# /etc/cron*
# /var/spool/cron*
def cron():
    #result = subprocess.check_output("echo 'test an input' | grep test", stderr=subprocess.STDOUT, shell=True)
    #print(result)
    pass

def ipv4Change(recipe):
    print(recipe)
    if recipe.key == 'add_one-time':
        # add at for ipv4 change playbook
        at()
        pass
    elif recipe.key == 'remove_one-time':
        # remove at for ipv4 change playbook
        cron()
        pass
    elif recipe.key == 'add_re-occurring':
        # add cron for ipv4 change playbook
        pass
    elif recipe.key == 'remove_re-occurring':
        # remove cron for ipv4 change playbook
        pass

    pass

def ipv6Change(recipe):
    pass

def dnsChange(recipe):
    pass

def addToFinalJson(recipe, operation):
    if recipe.host not in finalJson:
        finalJson[recipe.host] = {}
    if str(recipe.startTime) not in finalJson[recipe.host]:
        finalJson[recipe.host][str(recipe.startTime)] = []
    operation['key'] = recipe.key + '_' + 'start'
    print('*1', operation)
    finalJson[recipe.host][str(recipe.startTime)].append(operation)

    if recipe.endTime != None:
        if str(recipe.endTime) not in finalJson[recipe.host]:
            finalJson[recipe.host][str(recipe.endTime)] = []
        operation = operation.copy()
        operation['key'] = recipe.key + '_' + 'end'
        print('*2', operation)
        finalJson[recipe.host][str(recipe.endTime)].append(operation)

def parseOperatios(operations, recipe):
    for operation in operations:
        if 'name' not in operation:
            print("[OPERATION] >> name not defined for this operation")
            continue
        if 'current' not in operation:
            print("[OPERATION] >> current value not defined for this operation")
            continue
        if 'requested' not in operation:
            print("[OPERATION] >> requested value not defined for this operation")
            continue

        if operation['name'] == 'ipv4Change':
            print('ipv4Change')
            #ipv4Change(recipe)
            addToFinalJson(recipe, operation)
        elif operation['name'] == 'ipv6Change':
            print('ipv6Change')
            #ipv6Change(recipe)
            addToFinalJson(recipe, operation)
        elif operation['name'] == 'dnsChange':
            print('dnsChange')
            #dnsChange(recipe)
            addToFinalJson(recipe, operation)
        else:
            print('[OPERATION] >> unsupported operation', operation)

def getRequests():
    print("[SYNC] start")

    connection = mysql.connector.connect(user='root', password='empowered',
                                  host='192.168.158.68',
                                  database='rbc_ddi_automation')

    cursor = connection.cursor()

    query = ("SELECT * FROM ddi_change_request "
             "WHERE id > %s AND id < %s")

    idMin = 0
    idMax = 100
    cursor.execute(query, (idMin, idMax))

    Recipe = namedtuple("Recipe", "key host startTime endTime")

    for (id, host, start_time, end_time, type, action, operations) in cursor:
        print("***************\n")
        print("[ddi_change_request {}] >> host = {}, start = {}, end = {}, type = {}, action = {}, operations = {}".format(
            id, host, start_time, end_time, type, action, operations))

        if action == 'cancel':
            print("[CANCELED] >> ignoring ddi_change_request id: {}.".format(id))
            continue

        try:
            operationsJson = json.loads(operations)
        except:
            print("[JSON error] ", sys.exc_info()[0])
            traceback.print_exc(file=sys.stdout)
            continue
        finally:
            pass

        if not isinstance(operationsJson, list):
            print("[OPERATIONS] >> operations need to be JSON array")
            continue

        # if type(operationsJson) != list:
        #     print("operations need to be JSON array")
        #     pass

        now_time = datetime.datetime.now()
        if now_time > start_time:
            print("[TIME] >> start time has passed")
            continue

        if (end_time != None) and (now_time > end_time):
            print("[TIME] >> end time has passed")
            continue

        if host == None or host == '':
            print("[HOST] >> no target host defined")
            continue

        if type == 'one-time':
            if action == 'add':
                print('add at')
                recipe = Recipe(key='add_one-time', host=host, startTime=start_time, endTime=end_time)
                parseOperatios(operationsJson, recipe)

            elif action == 'remove':
                print('remove at')
                recipe = Recipe(key='remove_one-time', host=host, startTime=start_time, endTime=end_time)
                parseOperatios(operationsJson, recipe)

            else:
                print("[ACTION] >> unsupported action", action)

        elif type == 're-occurring':
            if action == 'add':
                print('add cron')
                recipe = Recipe(key='add_re-occurring', host=host, startTime=start_time, endTime=end_time)
                parseOperatios(operationsJson, recipe)

            elif action == 'remove':
                print('remove cron')
                recipe = Recipe(key='remove_re-occurring', host=host, startTime=start_time, endTime=end_time)
                parseOperatios(operationsJson, recipe)

            else:
                print("[ACTION] >> unsupported action", action)

        else:
            print("[TYPE] >> unsupported type", type)

    cursor.close()

# now store the data
    global finalJson
    print(finalJson)
    finalJsonString = json.dumps(finalJson)
    print('finalJSON', finalJsonString)

    cursor = connection.cursor()

    cursor.execute(("TRUNCATE TABLE cron_operation"), ())

    connection.commit()

    cursor.close()


    cursor = connection.cursor()

    cronOperationInsert = ("INSERT INTO cron_operation "
                           "(host, time, operation, current, requested) "
                           "VALUES (%s, %s, %s, %s, %s)")

    for host in finalJson:
        #print(host)
        for thisTime in finalJson[host]:
            #print(thisTime)
            for operation in finalJson[host][thisTime]:
                #print(operation)
                data = (host, thisTime, operation['key'] +'_'+ operation['name'], operation['current'], operation['requested'])
                print(data)
                cursor.execute(cronOperationInsert, data)

    connection.commit()

    cursor.close()

    finalJson = {}


    connection.close()

    print("[SYNC] end")
    print("\n-----------------------------------------\n")



class Cycle(threading.Thread):
    def __init__(self, interval):
        threading.Thread.__init__(self)
        self.interval = interval

    def run(self):
        print("starting cycle")
        while True:
            getRequests()
            time.sleep(60 * self.interval)


# minutes
interval = 1
syncCycle = Cycle(interval)
syncCycle.start()


#getRequests()


print("started")