#! /bin/bash

#/**
# * @author Manvinder Boparai
# * @version 01 Nov 2018
# * @filename start.sh
# *
# * run as sudo
# * restarts the main and cron scripts
# * main parses data and stores in cron table
# * cron_interface parses cron table and creates crontab entries
# *
# * Copyright 2018 Empowered Networks Inc.
# */


PYTHON_BINARY='/usr/bin/python'
MAIN_SCRIPT='main.py'
CRON_SCRIPT='cron_interface.py'
OUR_HOME=`dirname "$(readlink -f "$0")"`
LOGS_DIR=$OUR_HOME"/logs"
PIDS_DIR=$OUR_HOME"/pids"

MAIN_SCRIPT_PATH=$OUR_HOME"/"$MAIN_SCRIPT
CRON_SCRIPT_PATH=$OUR_HOME"/"$CRON_SCRIPT
MAIN_LOGS_PATH=$LOGS_DIR"/"$MAIN_SCRIPT".log"
CRON_LOGS_PATH=$LOGS_DIR"/"$CRON_SCRIPT".log"
MAIN_PID_PATH=$PIDS_DIR"/"$MAIN_SCRIPT".pid"
CRON_PID_PATH=$PIDS_DIR"/"$CRON_SCRIPT".pid"

set +e
kill -15 $(cat $MAIN_PID_PATH) > /dev/null 2>&1
kill -15 $(cat $CRON_PID_PATH) > /dev/null 2>&1

for pid in $( ps -ef | grep -v grep | grep  "$MAIN_SCRIPT_PATH\|$CRON_SCRIPT_PATH" | awk '{print $2}')
do
    #echo $pid
    kill -9 $pid > /dev/null 2>&1
done
set -e

sleep 1

cd $OUR_HOME && $PYTHON_BINARY $MAIN_SCRIPT_PATH >> $MAIN_LOGS_PATH 2>&1 &
MAIN_PID=$(pgrep -P $!)
echo "$MAIN_PID" > $MAIN_PID_PATH
echo "[$MAIN_PID] $PYTHON_BINARY $MAIN_SCRIPT_PATH >> $MAIN_LOGS_PATH 2>&1"

sleep 1

cd $OUR_HOME && $PYTHON_BINARY $CRON_SCRIPT_PATH >> $CRON_LOGS_PATH 2>&1 &
CRON_PID=$(pgrep -P $!)
echo "$CRON_PID" > $CRON_PID_PATH
echo "[$CRON_PID] $PYTHON_BINARY $CRON_SCRIPT_PATH >> $CRON_LOGS_PATH 2>&1"
