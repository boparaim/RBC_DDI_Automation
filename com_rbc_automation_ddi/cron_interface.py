import datetime
import io
import re
import subprocess
import threading
import time

import mysql.connector
import yaml


# utility function to print a log message
def log(tag, msg):
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")+' - ['+tag.upper()+'] >> '+msg)


log('start', 'com_rbc_automation_ddi/cron_interface.py')

# read properties file
settings = yaml.safe_load(io.open('properties.yaml', 'r', encoding='utf-8'))
#print(yaml.dump(settings), settings)

crontabFile = settings['cron_interface']['crontab_file']
username = settings['cron_interface']['cron_username']
ansibleHome = settings['cron_interface']['ansible_directory']
ansiblePlaybook = settings['cron_interface']['main_playbook']
ansibleBinary = settings['cron_interface']['ansible_playbook_binary']
ansibleVaultPasswordFile = settings['cron_interface']['ansible_vault_password_file']
logFileName = settings['cron_interface']['log_file']

connection = None


# remove previous entries
def remove_previous_entries():
    result = subprocess.check_output("perl -pi -0 -e 's/\n\n# RBC DDI Utility//g' "+crontabFile,
                                     stderr=subprocess.STDOUT, shell=True)
    #print(result)

    result = subprocess.check_output("perl -pi -0 -e 's/\n\n# RBC DDI Cron Entry[\n\r]+.*//g' "+crontabFile,
                                     stderr=subprocess.STDOUT, shell=True)
    #print(result)


# add title line to crontab
def add_title_comment():
    result = subprocess.check_output("echo '\n# RBC DDI Utility' >> "+crontabFile,
                                     stderr=subprocess.STDOUT, shell=True)
    #print(result)


def add_cron_entries():
    global connection
    connection = mysql.connector.connect(
                    user=settings['database']['username'],
                    password=settings['database']['password'],
                    host=settings['database']['host'],
                    port=settings['database']['port'],
                    database=settings['main']['source_schema'])

    cursor = connection.cursor()

    get_cron_operations_query = ("SELECT DISTINCT host, time, operation, current, requested"
                                 " FROM `{}`"
                                 " WHERE operation REGEXP 'add_'"
                                 " ORDER BY time, host").format(settings['cron_interface']['source_table'])

    cursor.execute(get_cron_operations_query, ())

    for (host, time, operation, current, requested) in cursor:
        log('cron_operation', '{} - time = {}, operation = {}, current = {}, requested = {}'
            .format(host, time, operation, current, requested))

        minute = hour = day_of_month = month = day_of_week = '*'

        playbook_name = ''
        if re.match(r".*_ipv4Change$", operation):
            playbook_name = 'change-ipv4'
        elif bool(re.match(r".*_ipv6Change$", operation)) is True:
            playbook_name = 'change-ipv6'
        elif bool(re.match(r".*_dnsChange$", operation)) is True:
            playbook_name = 'change-dns'
        else:
            log('operation', 'unsupported operation ' + operation)
            continue

        if re.match(r".*_end_.*", operation):
            if playbook_name == 'change-ipv4' or playbook_name == 'change-ipv6':
                host = requested
            temp = current
            current = requested
            requested = temp

        regexp_match_once = re.match(r"(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)", str(time))
        regexp_match_reoccurring = re.match(r"([*-/\d]+) ([*-/\d]+) ([*-/\d]+) ([*-/\d]+) ([*-/\d]+)", str(time))
        #print('match', bool(regexp_match_once), regexp_match_once)
        #print('match', bool(regexp_match_reoccurring), regexp_match_reoccurring)

        if bool(regexp_match_once) is True:
            month = regexp_match_once.group(2)
            day_of_month = regexp_match_once.group(3)
            hour = regexp_match_once.group(4)
            minute = regexp_match_once.group(5)

        elif bool(regexp_match_reoccurring) is True:
            minute = regexp_match_reoccurring.group(1)
            hour = regexp_match_reoccurring.group(2)
            day_of_month = regexp_match_reoccurring.group(3)
            month = regexp_match_reoccurring.group(4)
            day_of_week = regexp_match_reoccurring.group(5)

        else:
            log('time', 'unsupported time format')
            continue

        result = subprocess.check_output("echo '\n# RBC DDI Cron Entry' >> "+crontabFile,
                                         stderr=subprocess.STDOUT, shell=True)
        #print(result)

        result = subprocess.check_output("echo '"+minute+" "+hour
                                         +" "+day_of_month+" "+month+" "+day_of_week+" "+username
                                         +" cd "+ansibleHome+" &&"
                                         +" "+ansibleBinary
                                         +" "+ansiblePlaybook
                                         +" -i \'"+host+",\'"
                                         +" --extra-vars \"operation="+playbook_name
                                         +" from="+current+" to="+requested+"\""
                                         +" --vault-password-file "+ansibleVaultPasswordFile
                                         +" --forks 5"
                                         +" --timeout 30 >> "+logFileName+" 2>&1"
                                         +"' >> "+crontabFile, stderr=subprocess.STDOUT, shell=True)
        #print(result)

    cursor.close()


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
            remove_previous_entries()
            add_title_comment()
            add_cron_entries()
            connection.close()
            log('sync', 'end')
            print("-----------------------------------------\n")

            time.sleep(60 * self.interval)


# start the infinite loop
syncCycle = Cycle(settings['main']['interval'])
syncCycle.start()





# ctrl+shift+f1 to sync with remote
# ansible-vault create password.yaml
# sudo python cron_interface.py >> logs/cron_interface.log &

# test results on server:
# while :; do echo $(date); ip a | grep 192; sleep 60; done