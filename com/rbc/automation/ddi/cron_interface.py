import mysql.connector
import subprocess

connection = mysql.connector.connect(user='root', password='empowered',
                                  host='192.168.158.68',
                                  database='rbc_ddi_automation')

cursor = connection.cursor()

query = ("SELECT * FROM cron_operation "
         "WHERE operation REGEXP 'add_one-time'"
         "ORDER BY time, host")

cursor.execute(query, ())

for (id, host, time, operation, current, required) in cursor:
    print("***************\n")
    print("[cron_operation {}] >> host = {}, time = {}, operation = {}, current = {}, required = {}".format(
        id, host, time, operation, current, required))

    result = subprocess.check_output("echo 'test an input' | grep test", stderr=subprocess.STDOUT, shell=True)
    print(result)

cursor.close()

connection.close()

print("[SYNC] end")
print("\n-----------------------------------------\n")
