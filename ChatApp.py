#Student name and No.: Lin Jianan, 3035577595
#Development platform: Windows 10
#Python version: Python 3.8.6
#Required program: ChatApp.py, chatServer.py
#ChapApp.py: client of chat software.
#Client can send message to himself/herself.
#Client will also receive the message he/she types after broadcasting.
#Important events e.g. broken connection, successful connection, fails connection, receives messages from server, leaving chatroom. will be displayed in console.
#Peer list, broken connection, leaving chatroom will be displayed by list_print().
#Be patient when clicking buttons 'JOIN' and 'LEAVE'. It takes 1 ~ 2 seconds to complete execution.
#This program assumes that user lways click button 'LEAVE' before closing chat window.

#!/usr/bin/python3

from tkinter import *
from tkinter import ttk
from tkinter import font
import sys
import socket
import json
import os
import threading
import time

#
# Global variables
#
USERID = None
NICKNAME = None
SERVER = None
SERVER_PORT = None
#buffer size of received messages.
buff_sz = 256
#Thread handling asynchronous messages from server
client_thread = None
#socket for communication
client_socket = None
#Peer list, format: {UID: nickname}
peer_list = {}

#
# Functions to handle user input
#

class clientThread(threading.Thread):
  def __init__(self, socket):
    global client_socket
    threading.Thread.__init__(self)
    #Keep a copy of thread
    self.t = None
    #Continue running this thread until this is et to be False.
    self.cont = True 
    client_socket.settimeout(1.0)

  #Main program of thread
  def listen(self):
    global client_socket
    global peer_list
    while self.cont:
      try:
        data = client_socket.recv(buff_sz)
        if len(data) > 0:
          #Interpret meaningful messages.
          try:
            data = json.loads(data.decode('ascii'))
          #Ignore not meaningful messages.
          except json.decoder.JSONDecodeError:
            console_print(NICKNAME + "receives innvalid message.")
            continue
          console_print(NICKNAME + " receives message:\n" + str(data))
          #Check if data is peer list.
          if data["CMD"] == "LIST":
            #Format conversion: [{"UN": y, "UID": x}] -> {x: y}
            peer_list = dict([(lambda x: (x[1], x[0]))(list(e.values())) for e in data["DATA"]])
            #Show updated peer list on UI interface.
            list_print(', '.join([name + ' (' + id + ')' for id, name in peer_list.items()]))
          #Check if data is peer message.
          #Handle private, group, & broadcast messages
          elif data["CMD"] == "MSG":
            #Format of peers' message see 2021-22-Programming-Briefing.pdf, 25 / 29
            #Display the message
            if data["TYPE"] == "PRIVATE":
              chat_print("[" + peer_list[data["FROM"]] + "] " + data["MSG"], "redmsg")
            if data["TYPE"] == "GROUP":
              chat_print("[" + peer_list[data["FROM"]] + "] " + data["MSG"], "greenmsg")
            if data["TYPE"] == "ALL":
              chat_print("[" + peer_list[data["FROM"]] + "] " + data["MSG"], "bluemsg")
        else:
          #Seems connection is broken. Try reconnection.
          self.check_connection()
      except (socket.timeout, ConnectionResetError, ConnectionAbortedError):
        #Seems connection is broken. Try reconnection.
        self.check_connection()

  def check_connection(self):
    #Test if client is connected
    try:
      test_msg = {"CMD": "SEND", "MSG": "TEST", "TO": ["INVALID"], "FROM": USERID}
      client_socket.send(json.dumps(test_msg).encode('ascii'))
    #Cannot connect to server
    except socket.error: 
      #Remind user that he/she is disconnected.
      list_print("You are disconnected. Click 'join' to rejoin.\nMake sure server is running.")
      console_print("You are disconnected. Click 'join' to rejoin.\nMake sure server is running.")
      #Stop this thread
      self.cont = False

  #Start main program of thread.
  def start_listen(self):
    self.t = threading.Thread(target = self.listen)
    self.t.start()

  #Stop main program of thread
  def stop_listen(self):
    self.t.join()

def do_Join():
  global client_thread
  global client_socket
  global peer_list

  #Set up socket
  try:
    #Not sure if this connection will success. So, set up temporary socket first. 
    temp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    temp_client_socket.settimeout(2.0)
    #join the Chatserver
    temp_client_socket.connect((SERVER, SERVER_PORT))
    #Send join command to server.
    join_cmd = {"CMD": "JOIN", "UN": NICKNAME, "UID": USERID}
    join_cmd = json.dumps(join_cmd)
    temp_client_socket.send(rf'{join_cmd}'.encode('ascii'))
    #Receive ack command from server
    ack = temp_client_socket.recv(buff_sz) #Wait fro ACK from server
    ack = ack.decode('ascii')
    ack = json.loads(ack)
    if ack["CMD"] == 'ACK':
      #Connetion is successful. Set temporary socket to be final one.
      if ack["TYPE"] == "OKAY":
        client_socket = temp_client_socket
        #Receive peer list.
        peer_info = client_socket.recv(buff_sz)
        peer_info = json.loads(peer_info.decode('ascii'))
        if peer_info["CMD"] == "LIST":
          peer_list = {}
          for info in peer_info["DATA"]:
            peer_list[info["UID"]] = info["UN"]
        #show peer list on chat window.
        list_print(', '.join([name + ' (' + id + ')' for id, name in peer_list.items()]))
        console_print(NICKNAME + " join success.")

        #Before starting new thread, close any existing thread.
        #We just need 2 threads. 1 handles asynchrnous messages. 1 handles buttons of UI interface.
        if client_thread != None:
          client_thread.cont = False
          time.sleep(1)
        #Start thread, which receives asynchronous peer list and message from peers.
        client_thread = clientThread(client_socket)
        client_thread.start_listen()
        #Show that connection is successful
        return 1
      else: #This client repeat joining.
        console_print(NICKNAME + " join fails. Either this is already connected to server, or try connecting again.")
        #Show that connection fails.
        return 0
  except (socket.error, ConnectionRefusedError):
    #detect a failure in joining
    console_print("Socket error: timed out, cannot join chat Server.")
    #Show that connection fails.
    return 0

def do_Send():
  global client_thread
  global client_socket

  #Check the TO:  fields
  tolist = get_tolist()
  #Check the message fields
  sendmsg = get_sendmsg()

  #Do not accept empty "TO: " field and empty "message" field.
  if sendmsg == '\n' or tolist == '':
    console_print("BOTH 'TO' field and 'message' field should be non-empty.")
    return

  #Can identify input user IDs separated by ",", regardless whitespace.
  if tolist.strip() == 'ALL':
    tolist = []
  else:
    tolist = [e.strip() for e in tolist.split(',')] 

  #Make Send command
  send_cmd = {"CMD": "SEND", "TO": tolist, "MSG": sendmsg, "FROM": USERID}
  try:
    client_socket.send(json.dumps(send_cmd).encode('ascii'))
    console_print(NICKNAME + " sends message:\n" + str(send_cmd))
  except:
    #Tell user that connection is broken
    console_print("Connect to the server first before sending messages.")
    return

  #Display message on UI interface.
  if len(tolist) == 0:
    #to all people
    chat_print("[To: ALL] " + sendmsg)
  elif len(tolist) == 1:
    #only 1 recipient, who is not in peer list.
    if tolist[0] not in peer_list.values():
      console_print("The peer is NOT in peer list.")
      return
    #only 1 recipient, who is in peer list.
    else:
      peer_nicknames = [name for name in tolist if name in peer_list.values()]
      chat_print("[To: " + ", ".join(peer_nicknames) + "] " + sendmsg)
  #Send to >1 people.
  else: 
    peer_nicknames = [name for name in tolist if name in peer_list.values()]
    chat_print("[To: " + ", ".join(peer_nicknames) + "] " + sendmsg)


def do_Leave():
  #The following statement is just for demo purpose
  #Remove it when you implement the function
  global client_thread
  global client_socket

  #Clear peer list
  peer_list = {}


  #Stop thread, if there is any.
  if client_thread != None:
    client_thread.cont = False 
    time.sleep(1)
    client_thread = None
    print(NICKNAME, "stops thread.")
  else:
    print(NICKNAME, "client_thread = None")

  #Send command to server, request breaking connection.
  try:
    #Close the TCP connection
    client_socket.send(json.dumps({"CMD": "TEST"}).encode('ascii'))
    client_socket.close()
    console_print(NICKNAME + " leaves successfully.")
    #Remind user that he/she leaves
    list_print("You leave.")
    console_print("You leave.")
  except (AttributeError, OSError):
    #Allow user to rejoin the Chatserver
    console_print(NICKNAME + " has already left.")

#################################################################################
#Do not make changes to the following code. They are for the UI                 #
#################################################################################

#for displaying all log or error messages to the console frame
def console_print(msg):
  console['state'] = 'normal'
  console.insert(1.0, "\n"+msg)
  console['state'] = 'disabled'

#for displaying all chat messages to the chatwin message frame
#message from this user - justify: left, color: black
#message from other user - justify: right, color: red ('redmsg')
#message from group - justify: right, color: green ('greenmsg')
#message from broadcast - justify: right, color: blue ('bluemsg')
def chat_print(msg, opt=""):
  chatWin['state'] = 'normal'
  chatWin.insert(1.0, "\n"+msg, opt)
  chatWin['state'] = 'disabled'

#for displaying the list of users to the ListDisplay frame
def list_print(msg):
  ListDisplay['state'] = 'normal'
  #delete the content before printing
  ListDisplay.delete(1.0, END)
  ListDisplay.insert(1.0, msg)
  ListDisplay['state'] = 'disabled'

#for getting the list of recipents from the 'To' input field
def get_tolist():
  msg = toentry.get()
  toentry.delete(0, END)
  return msg

#for getting the outgoing message from the "Send" input field
def get_sendmsg():
  msg = SendMsg.get(1.0, END)
  SendMsg.delete(1.0, END)
  return msg

#for initializing the App
def init():
  global USERID, NICKNAME, SERVER, SERVER_PORT


  #check if provided input argument
  if (len(sys.argv) > 2):
    print("USAGE: ChatApp [config file]")
    sys.exit(0)
  elif (len(sys.argv) == 2):
    config_file = sys.argv[1]
  else:
    config_file = "config.txt"

  #check if file is present
  if os.path.isfile(config_file):
    #open text file in read mode
    text_file = open(config_file, "r")
    #read whole file to a string
    data = text_file.read()
    #close file
    text_file.close()
    #convert JSON string to Dictionary object
    config = json.loads(data)
    USERID = config["USERID"].strip()
    NICKNAME = config["NICKNAME"].strip()
    SERVER = config["SERVER"].strip()
    SERVER_PORT = config["SERVER_PORT"]
  else:
    print("Config file not exist\n")
    sys.exit(0)


if __name__ == "__main__":
  init()

#
# Set up of Basic UI
#
win = Tk()
win.title("ChatApp")

#Special font settings
boldfont = font.Font(weight="bold")

#Frame for displaying connection parameters
topframe = ttk.Frame(win, borderwidth=1)
topframe.grid(column=0,row=0,sticky="w")
ttk.Label(topframe, text="NICKNAME", padding="5" ).grid(column=0, row=0)
ttk.Label(topframe, text=NICKNAME, foreground="green", padding="5", font=boldfont).grid(column=1,row=0)
ttk.Label(topframe, text="USERID", padding="5" ).grid(column=2, row=0)
ttk.Label(topframe, text=USERID, foreground="green", padding="5", font=boldfont).grid(column=3,row=0)
ttk.Label(topframe, text="SERVER", padding="5" ).grid(column=4, row=0)
ttk.Label(topframe, text=SERVER, foreground="green", padding="5", font=boldfont).grid(column=5,row=0)
ttk.Label(topframe, text="SERVER_PORT", padding="5" ).grid(column=6, row=0)
ttk.Label(topframe, text=SERVER_PORT, foreground="green", padding="5", font=boldfont).grid(column=7,row=0)


#Frame for displaying Chat messages
msgframe = ttk.Frame(win, relief=RAISED, borderwidth=1)
msgframe.grid(column=0,row=1,sticky="ew")
msgframe.grid_columnconfigure(0,weight=1)
topscroll = ttk.Scrollbar(msgframe)
topscroll.grid(column=1,row=0,sticky="ns")
chatWin = Text(msgframe, height='15', padx=10, pady=5, insertofftime=0, state='disabled')
chatWin.grid(column=0,row=0,sticky="ew")
chatWin.config(yscrollcommand=topscroll.set)
chatWin.tag_configure('redmsg', foreground='red', justify='right')
chatWin.tag_configure('greenmsg', foreground='green', justify='right')
chatWin.tag_configure('bluemsg', foreground='blue', justify='right')
topscroll.config(command=chatWin.yview)

#Frame for buttons and input
midframe = ttk.Frame(win, relief=RAISED, borderwidth=0)
midframe.grid(column=0,row=2,sticky="ew")
JButt = Button(midframe, width='8', relief=RAISED, text="JOIN", command=do_Join).grid(column=0,row=0,sticky="w",padx=3)
QButt = Button(midframe, width='8', relief=RAISED, text="LEAVE", command=do_Leave).grid(column=0,row=1,sticky="w",padx=3)
innerframe = ttk.Frame(midframe,relief=RAISED,borderwidth=0)
innerframe.grid(column=1,row=0,rowspan=2,sticky="ew")
midframe.grid_columnconfigure(1,weight=1)
innerscroll = ttk.Scrollbar(innerframe)
innerscroll.grid(column=1,row=0,sticky="ns")
#for displaying the list of users
ListDisplay = Text(innerframe, height="3", padx=5, pady=5, fg='blue',insertofftime=0, state='disabled')
ListDisplay.grid(column=0,row=0,sticky="ew")
innerframe.grid_columnconfigure(0,weight=1)
ListDisplay.config(yscrollcommand=innerscroll.set)
innerscroll.config(command=ListDisplay.yview)
#for user to enter the recipents' Nicknames
ttk.Label(midframe, text="TO: ", padding='1', font=boldfont).grid(column=0,row=2,padx=5,pady=3)
toentry = Entry(midframe, bg='#ffffe0', relief=SOLID)
toentry.grid(column=1,row=2,sticky="ew")
SButt = Button(midframe, width='8', relief=RAISED, text="SEND", command=do_Send).grid(column=0,row=3,sticky="nw",padx=3)
#for user to enter the outgoing message
SendMsg = Text(midframe, height='3', padx=5, pady=5, bg='#ffffe0', relief=SOLID)
SendMsg.grid(column=1,row=3,sticky="ew")

#Frame for displaying console log
consoleframe = ttk.Frame(win, relief=RAISED, borderwidth=1)
consoleframe.grid(column=0,row=4,sticky="ew")
consoleframe.grid_columnconfigure(0,weight=1)
botscroll = ttk.Scrollbar(consoleframe)
botscroll.grid(column=1,row=0,sticky="ns")
console = Text(consoleframe, height='10', padx=10, pady=5, insertofftime=0, state='disabled')
console.grid(column=0,row=0,sticky="ew")
console.config(yscrollcommand=botscroll.set)
botscroll.config(command=console.yview)

win.mainloop()
