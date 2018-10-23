import mysql.connector
import subprocess
import re

crontabFile = '/etc/crontab'
username = 'boparaim'
ansibleHome = '/home/boparaim/rbc-util/ansible/'

# ctrl+shift+f1 to sync with remote

# remove previous entries
#result = subprocess.check_output("sed -i -e 's/# RBC Utility//g' "+crontabFile, stderr=subprocess.STDOUT, shell=True)
#print(result)
result = subprocess.check_output("perl -pi -0 -e 's/\n\n# RBC Utility//g' "+crontabFile, stderr=subprocess.STDOUT, shell=True)
print(result)

result = subprocess.check_output("perl -pi -0 -e 's/\n\n# RBC Cron Entry[\n\r]+.*//g' "+crontabFile, stderr=subprocess.STDOUT, shell=True)
print(result)

# add an empty line to crontab
result = subprocess.check_output("echo '\n# RBC Utility' >> "+crontabFile, stderr=subprocess.STDOUT, shell=True)
print(result)



connection = mysql.connector.connect(user='root', password='empowered',
                                  host='192.168.158.68', port='3306',
                                  database='rbc_ddi_automation')

cursor = connection.cursor()

query = ("SELECT * FROM cron_operation "
         "WHERE operation REGEXP 'add_one-time'"
         "ORDER BY time, host")

cursor.execute(query, ())

for (id, host, time, operation, current, requested) in cursor:
    print("***************\n")
    print("[cron_operation {}] >> host = {}, time = {}, operation = {}, current = {}, requested = {}".format(
        id, host, time, operation, current, requested))

    rexpMatch = re.match(r"(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)", str(time))
    print('match', bool(rexpMatch))
    if bool(rexpMatch) == True:
        print(rexpMatch.group(0), rexpMatch.group(1))

        year = rexpMatch.group(1)
        month = rexpMatch.group(2)
        day = rexpMatch.group(3)
        hour = rexpMatch.group(4)
        minute = rexpMatch.group(5)
        second = rexpMatch.group(6)

    result = subprocess.check_output("echo '\n# RBC Cron Entry' >> "+crontabFile, stderr=subprocess.STDOUT, shell=True)
    print(result)
    result = subprocess.check_output("echo '"+minute+" "+hour+" "+day+" "+month+" * "+username
                                     +" cd "+ansibleHome+" &&"
                                     +" ansible-playbook change-ipv4.yaml -i '"+host
                                     +",' --extra-vars \"from="+current+" to="+requested+"\""
                                     +"' >> "+crontabFile, stderr=subprocess.STDOUT, shell=True)
    #ansible-playbook change-ipv4.yaml -i '192.168.78.132,' --extra-vars "from=192.168.78.132 to=192.168.78.134"
    # ansible-playbook change-ipv4.yaml -i '192.168.78.132,' --extra-vars "from=192.168.78.132 to=192.168.78.134" --vault-password-file vaul-password.yaml
    #ansible-playbook change-ipv4.yaml -i '192.168.78.132,' --extra-vars "from=192.168.78.132 to=192.168.78.134" --vault-password-file vaul-password.yaml --forks 5 --timeout 30
    print(result)

cursor.close()

connection.close()

print("[SYNC] end")
print("\n-----------------------------------------\n")
