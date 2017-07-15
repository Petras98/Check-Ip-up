import os
import time
#Slack API. Used for connecting the bot to the slack channels
from slackclient import SlackClient
#User for multithreading
import threading
from queue import Queue
#Used for checking how long to check the file
import datetime
#Used for pinging
import subprocess

#The bot id found in another script
BOT_ID = "BOTID"

#The bot token
SLACK_BOT_TOKEN = "SLACKBOTTOKEN"

AT_BOT = "<@" + BOT_ID + ">"


#The channel the bot should send the down ip's to. 
DOWN_IP_CHANNEL = "CHANNEL HERE"


#The bot will react to these
commands = {"example":"do"}

#For example, (if you have everything commented out for using commands), you could type '@mikrotikbot <command>'-
#and it would respond to the command with what it is supposed to. Note: The bot has to be in the channel to use it

#Sets how many threads should run at once for the ip check
#One extra thread will be running for the commmand listener (if active)
NUMBER_OF_THREADS = 8

READ_WEBSOCKET_DELAY = 30 #How long before the bot checks ips again

HOW_LONG_BEFORE_STORING_FILE = 30 #How long before storing the down ip list into a file

#used for controlling whats on and off. Can be changed using commands from the channel (Not sure why that would be needed, but it will work)
checking_ips_on = True
command_listen_on = True

slack_client = SlackClient(SLACK_BOT_TOKEN)

#Every ip that is down in a certain time period will be put in this set.
#After an amount of time, every ip in this set, with a timestamp, will be put into a file, where every ip that has been down will be saved.
temporary_down_ip_holder = set()



#Reading ip address' files. 
def file_to_set(file_name):
    results = set()
    #opens the file and reads each line into a set
    with open(file_name, 'rt') as f:
        for line in f:
            results.add(line.replace('\n', ''))
            
    return results

# Iterate through a set, each item will be a line in a file
def set_to_file(ip_addresses, file_name):
    with open(file_name,"w") as f:
        for l in sorted(ip_addresses):
            f.write(l+"\n")

def add_down_ip_to_perm_file():
    print("in adding file")
    with open("everyDownIp.txt", 'a') as file:
        for down_ip in sorted(temporary_down_ip_holder):
            file.write(down_ip + '\n')


#For pinging the ip
def ping(ip):
    #Returns True if the ip (str) responds to a ping request.
    ping = subprocess.call(['ping', '-c', '1', '-W', '0.5', ip],
                              stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))
    return ping == 0

def check_if_ip_down(which_ip, channel):
    if not ping(which_ip):
        temporary_down_ip_holder.add("{} down at: {}".format(datetime.datetime.now(), which_ip))
        
        response = "{} is down".format(which_ip)
        
        slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)
    #else:
        #print ("{} is up".format(which_ip)) #If you want to print to the shell line what ips are up, uncomment this else statement
        


#Threading start
queue = Queue()

# Create worker threads (will die when main exits)
def create_threads():
    for _ in range(NUMBER_OF_THREADS):
        t = threading.Thread(target=work)
        t.daemon = True
        t.start()

#Puts the thread to work by getting ip adr from the create_jobs func
#it then puts the current thread to 'work' by running the check_if_ip_down func with the ip recieved from the queue
def work():
    while checking_ips_on:
        ip = queue.get()
        check_if_ip_down(ip, DOWN_IP_CHANNEL)
        queue.task_done()

def create_jobs():
    #start_time = datetime.datetime.now() #will be used for checking how long it takes to run through every ip

    #Turns the ipAddresses file to a set, it then checks every ip and puts it in the queue, where the threads will-
    #pick it up from the work func
    for address in file_to_set("ipAddresses.txt"):
        if not(address in temporary_down_ip_holder):
            queue.put(address)
        else:
            pass
    queue.join()
    
    #end_time = datetime.datetime.now() #Part of the checking how long it takes
    #print (end_time - start_time)
#Threading end



#Next few functions are used for controlling the bot via commands recieved from the slack channel.

#Commands start
def create_thread_for_cmd():
    t = threading.Thread(target=command_listener)
    t.daemon = True
    t.start()

def command_listener():
    while command_listen_on:
        #can be used for controlling the bot from the slack channel
        #Also if you need to know the id of the channel
        command, channel = parse_slack_output(slack_client.rtm_read())
        
        if command and channel:
            handle_command(command, channel)
            print (channel)

        time.sleep(1)


def handle_command(command, channel):
        #Receives commands directed at the bot and determines if they
        #are valid commands. If so, then acts on the commands. If not,
        #returns back what it needs for clarification.
    
    response = "Not sure what you mean."
    
    if command.startswith(commands["example"].lower()):
        response = "Exmaple command response"
        
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


def parse_slack_output(slack_rtm_output):
    
        #The Slack Real Time Messaging API is an events firehose.
        #this parsing function returns None unless a message is
        #directed at the Bot, based on its ID.
    
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel']
    return None, None
#Commands end


if __name__ == "__main__":
    
    if slack_client.rtm_connect():
        print("MikroTikBot connected and running!")

        #we will subtract this from an file_store_end_time var to check if it is > then the HOW_LONG_BEFORE_STORING_FILE var.
        file_store_start_time = time.time()
        
        #Start the thread for commands listening
        create_thread_for_cmd()
        
        while checking_ips_on:
            #starting the threads for ip checking 
            create_threads()
            create_jobs()
            
            file_store_end_time = time.time()

            #checks if the timer is larger than the HOW_LONG_BEFORE_STORING_FILE, variable. For example if HOW_LONG_BEFORE_STORING_FILE is set to 30,
            #the file_store_end_time and file_store_start_time check if it's over 30 seconds. 
            if file_store_end_time - file_store_start_time > HOW_LONG_BEFORE_STORING_FILE:
                #This function adds every ip in the temporary_down_ip_holder set, then 
                add_down_ip_to_perm_file()
                #This clears the set of down ips
                temporary_down_ip_holder.clear()
                #resets the number
                file_store_start_time = time.time()
                
            #how long before running the loop again. This determines how long before the next ip checking begins
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
