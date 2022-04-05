#Student name and No.: Lin Jianan, 3035577595
#Development platform: Windows 10
#Python version: Python 3.8.6
#Required program: ChatApp.py, chatServer.py

#Chatserver.py: chat server
#Taken from workshop2
import socket
import sys
import select
import struct
import json
import threading
import time


#global variables
buff_sz = 256 #buffer size
#{socket: [user nickname, user ID]}
user_list = {}
# add the listening socket to the READ socket list
Rlist = []
# create an empty WRITE socket list
Clist = []
socket_in_thread = []
peer_list = {} #format: {UID: nickname}

class serverThread(threading.Thread):
  def __init__(self, server_socket):
    global Clist
    global Rlist
    threading.Thread.__init__(self)
    self.cont = True
    self.sockfd = server_socket

  #main program of thread
  def listen(self):
    global peer_list
    global user_list
    global Rlist
    global Clist
    while self.cont:
      print("Peer list:", peer_list.items())
      #use select to wait for any incoming connection requests or incoming messages or 5 seconds
      try:
        Rready, Wready, Eready = select.select(Rlist, [], [], 5)
      #If socket error happens, then end the program.
      except select.error as emsg:
        print("At select, caught an exception:", emsg)
        self.cont = False
      #If there is keyboard interrupt, then end the program.
      except KeyboardInterrupt:
        print("At select, caught the KeyboardInterrupt")
        self.cont = False
  
      #If there is incoming activities.
      if Rready:
        #for each socket in the READ ready list
        for sd in Rready:
          if sd == self.sockfd:
            #Establish new connection with client
            newfd, caddr = self.sockfd.accept()
            newfd.settimeout(30)
            #receive message from client.
            cmd = newfd.recv(buff_sz) 
            print("Server receives", cmd)
            #Server tries to interpret message from client.
            try:
              join_cmd = json.loads(cmd.decode('ascii'))
              if join_cmd['CMD'] == 'JOIN':
                #Allow client to join peer list if it has different nickname and user id.
                if join_cmd["UID"] not in peer_list.keys() and join_cmd["UN"] not in peer_list.values():
                  #Prepare and and send acknowledgement
                  ack_cmd = {"CMD": "ACK", "TYPE": "OKAY"}
                  ack_cmd = json.dumps(ack_cmd)
                  newfd.send(rf'{ack_cmd}'.encode('ascii')) #acknowledged.
                  #Update peer list
                  peer_list[join_cmd['UID']] = join_cmd['UN']
                  #Update user list
                  user_list[newfd] = [join_cmd['UN'], join_cmd['UID']]
                  #Send peer list to client
                  peer_cmd = {"CMD": "LIST", "DATA": [{"UN": y, "UID": x} for (x, y) in peer_list.items()]}
                  #Add new client to serving queue.
                  Rlist.append(newfd)
                  Clist.append(newfd)
                  #Send updated peer list to all clients
                  for c in Clist:
                    print("Server send updated peer list" , peer_list, "to", user_list[c][1])
                    c.send(json.dumps(peer_cmd).encode('ascii'))
                #Reject client to join peer list if it has same nickname or user id in peer list.
                else:
                  ack_cmd = {"CMD": "ACK", "TYPE": "FAIL"}
                  ack_cmd = json.dumps(ack_cmd)
                  newfd.send(rf'{ack_cmd}'.encode('ascii')) #acknowledged.
            #join command from client is corrupted. Server sends ACK = FAIL message.
            except json.decoder.JSONDecodeError:
              ack_cmd = {"CMD": "ACK", "TYPE": "FAIL"}
              ack_cmd = json.dumps(ack_cmd)
              newfd.send(rf'{ack_cmd}'.encode('ascii')) #acknowledged.
          else:
            #Receive message from client
            try:
              rmsg = sd.recv(500)
            except (ConnectionAbortedError, ConnectionResetError):
              #Probably client has disconnected. Try to delete it from peer list.
              self.remove_peer(sd)
            #Send peer list periodically to see if client is connected.
            peer_cmd = {"CMD": "LIST", "DATA": [{"UN": y, "UID": x} for (x, y) in peer_list.items()]}
            try:
              sd.send(json.dumps(peer_cmd).encode('ascii'))
            except:
              self.remove_peer(sd)
            #try:
            #  name = user_list[sd] #See if socket is in peer list
            #  print("Server repeats sending peer list.", user_list[sd])
            #except:
            #  print("Server repeats sending peer list.")
            if rmsg:
              #Decode meaningful message
              try: 
                rmsg = json.loads(rmsg.decode('ascii'))
                if rmsg['CMD'] == 'SEND':
                  if "INVALID" in rmsg["TO"]:
                    #This is message from client to test if client is connected.
                    #So, server has no need to take action.
                    pass
                  #Client request to broadcast message
                  elif len(rmsg["TO"]) == 0:
                    msg_cmd = {"CMD": "MSG", "TYPE": "ALL", "MSG": rmsg["MSG"], "FROM": rmsg["FROM"]}
                    for c in Clist: #Send updated peer list to other clients.
                      c.send(json.dumps(msg_cmd).encode('ascii'))
                  #Client request sending to specified clients.
                  else: 
                    #for usrID in rmsg["TO"]:
                    for usrname in rmsg["TO"]:
                      #find whether recipient is in peer_list/user_list.
                      for socket in user_list:
                        #Label message with correct message type.
                        if user_list[socket][0] == usrname:
                          if len(rmsg["TO"]) == 0:
                            msg_type = "ALL"
                          elif len(rmsg["TO"]) == 1:
                            msg_type = "PRIVATE"
                          else:
                            msg_type = "GROUP"
                          msg_cmd = {"CMD":"MSG", "TYPE": msg_type, "MSG": rmsg["MSG"], "FROM": rmsg["FROM"]}
                          #Then, send message to other clients.
                          socket.send(json.dumps(msg_cmd).encode('ascii'))
              #Ignore not meaningful message from client.
              except (json.decoder.JSONDecodeError, AttributeError): #The message from client is not meaningful
                pass
            else:
              #Seems a broken connection, checks whether this connection is associated with a registered peer
              print("A client connection", sd.getsockname(), "is broken!!")
              if sd in user_list.keys(): #connection is associated with a registered peer
                print("Server remove", user_list[sd], "from peer list")
                quitName = user_list[sd] #Debug
                peer_list.pop(user_list[sd][-1])
                user_list.pop(sd)
                Clist.remove(sd)
                Rlist.remove(sd)
                #Send command to update peer list
                peer_cmd = {"CMD": "LIST", "DATA": [{"UN": y, "UID": x} for (x, y) in peer_list.items()]}
                for c in Clist: #Send updated peer list to other clients.
                  print(quitName, "quits. Server send updated peer list", peer_list, "to", user_list[c][1])
                  c.send(json.dumps(peer_cmd).encode('ascii'))
              else: #connection is not associated with a registered peer
                print("Server close unknown socket")
                sd.close()
      # else did not have activity for 10 seconds, 
      # just print out "Idling"
      else:
        print("Idling")

  def remove_peer(self, sd):
    print("A client connection", sd.getsockname(), "is broken!!")
    #connection is associated with a registered peer
    if sd in user_list.keys():
      print("Server remove", user_list[sd], "from peer list")
      quitName = user_list[sd] #Debug
      peer_list.pop(user_list[sd][-1])
      user_list.pop(sd)
      Clist.remove(sd)
      Rlist.remove(sd)
      #Send command to update peer list of all clients.
      peer_cmd = {"CMD": "LIST", "DATA": [{"UN": y, "UID": x} for (x, y) in peer_list.items()]}
      for c in Clist: #Send updated peer list to other clients.
        print(quitName, "quits. Server send updated peer list", peer_list, "to", user_list[c][1])
        c.send(json.dumps(peer_cmd).encode('ascii'))
    #connection is not associated with a registered peer
    else:
      print("Server close unknown socket")
      sd.close()

  #Start main program of thread.
  def start_listen(self):
    t = threading.Thread(target = self.listen)
    t.start()
    print('started listen')

  #Stop main program of thread.
  def stop_listen(self):
    t.join()
    print('stopped listen')

  #Not useful function.
  def update_user_list():
    user_list = user_list

def main(argv):
	# set port number
	# default is 32342 if no input argument
	if len(argv) == 2:
		port = int(argv[1])
	else:
		port = 40600

	# create socket and bind
	sockfd = socket.socket(type = socket.SOCK_STREAM)
	try:
		sockfd.bind(('', port))
	except socket.error as emsg:
		print("Socket bind error: ", emsg)
		sys.exit(1)

	# set socket listening queue
	sockfd.listen(5)

	# add the listening socket to the READ socket list
	Rlist.append(sockfd)

	try:
		server_thread = serverThread(sockfd)
		server_thread.start_listen()
		while 1:
			time.sleep(100)
	except KeyboardInterrupt:
		server_thread.cont = False
		print('Server detects keyboard interrupt.\nTerminating in 5 seconds...')

if __name__ == '__main__':
	if len(sys.argv) > 2:
		print("Usage: chatserver [<Server_port>]")
		sys.exit(1)
	main(sys.argv)
