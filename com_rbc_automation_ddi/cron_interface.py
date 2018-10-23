import datetime
import mysql.connector
import subprocess
import re
import yaml
import threading
import time


# utility function to print a log message
def log(tag, msg):
    print(datetime.datetime.now(),' - ['+tag.upper()+'] >> '+msg)


log('start', 'com_rbc_automation_ddi/cron_interface.py')

# read properties file
settings = yaml.safe_load(open('properties.yaml', 'r', encoding='utf-8'))
#print(yaml.dump(settings), settings)

crontabFile = settings['cron_interface']['crontab_file']
username = settings['cron_interface']['cron_username']
ansibleHome = settings['cron_interface']['ansible_directory']
ansibleBinary = settings['cron_interface']['ansible_playbook_binary']
ansibleVaultPasswordFile = settings['cron_interface']['ansible_vault_password_file']

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
            .format(id, host, time, operation, current, requested))

        minute = hour = day_of_month = month = day_of_week = '*'
        regexp_match_once = re.match(r"(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)", str(time))
        regexp_match_reoccurring = re.match(r"([*-/\d]+) ([*-/\d]+) ([*-/\d]+) ([*-/\d]+) ([*-/\d]+)", str(time))
        print('match', bool(regexp_match_once), regexp_match_once)
        print('match', bool(regexp_match_reoccurring), regexp_match_reoccurring)

        playbook_name = ''
        if bool(re.match(r"_(ipv4Change)$", operation)) is True:
            playbook_name = 'ipv4'
        elif bool(re.match(r"_(ipv6Change)$", operation)) is True:
            playbook_name = 'ipv6'
        elif bool(re.match(r"_(dnsChange)$", operation)) is True:
            playbook_name = 'dns'
        else:
            log('operation', 'unsupported operation')
            continue

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

        result = subprocess.check_output("echo '\n# RBC Cron Entry' >> "+crontabFile,
                                         stderr=subprocess.STDOUT, shell=True)
        #print(result)

        result = subprocess.check_output("echo '"+minute+" "+hour
                                         +" "+day_of_month+" "+month+" "+day_of_week+" "+username
                                         +" cd "+ansibleHome+" &&"
                                         +" "+ansibleBinary
                                         +" change-"+playbook_name+".yaml"
                                         +" -i '"+host+",'"
                                         +" --extra-vars \"from="+current+" to="+requested+"\""
                                         +" --vault-password-file "+ansibleVaultPasswordFile
                                         +" --forks 5"
                                         +" --timeout 30"
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