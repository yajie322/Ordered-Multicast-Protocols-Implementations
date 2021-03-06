'''
	Implementation of FIFO, TOTAL, CASUAL ordering in mulitcast
	FIFO: vector logical time
	TOTAL: sequencer coordination
	CASUAL: vector timestamp
	
	Authors: Zezhi (Herry) Wang, Yajie (Angus) Zhao, Shikun (Jason) Wang
	Date: Mar 17, 2018
'''
import unicast
import time
import sys
from threading import Thread

config_map = unicast.config_map

class FifoMult:
	# basic multicast (str msg)
	def __basic(self, msg):
		for idx in xrange(self.maxServer):
			self.node.unicast_send(str(idx), msg)

	# deliever msg (str sender, str msg)
	def __deliever(self, sender, msg):
		self.num_deliver += 1
		if msg == 'bye':
			print "Listener is stopped, press ENTER to exit node."
			return True
		print "Receive \"%s\" from process %s with time %f" % ( msg, sender, time.time())
		return False

	# bool, if current node is still listening
	def isUp(self):
		return self.node.isRunning()

	# fifo multicast msg (str msg)
	def send(self, msg):
		# increment S by 1
		self.S_fifo += 1
		# piggy back S into msg
		val = {'seq':self.S_fifo, 'msg':msg}
		# basic multicast msg
		self.__basic(val)

	# handle received msg (str pid, dict msg)
	def recv(self, pid, data):
		sender, seq, msg = int(pid), data['seq'], data['msg']
		res = False
		# if S = R[q] + 1
		if seq == self.R_fifo[sender] + 1:
			# Fifo deliever msg
			res = self.__deliever(sender, msg)
			# increment R[q]
			self.R_fifo[sender] += 1
		# if S > R[q]
		elif seq > self.R_fifo[sender] + 1:
			# put msg in hold-back queue
			self.hbQueue.append((sender,seq,msg))
		# check msg in hold-back queue
		for i in xrange(len(self.hbQueue)):				
			for val in self.hbQueue:
				sender,seq,msg = val
				# if s = r[pid] + 1
				if seq == self.R_fifo[sender] + 1:
					# remove msg from hold back queue
					self.hbQueue.remove(val)
					# deliever msg
					res = self.__deliever(sender, msg)
					# increment r[pid] by 1
					self.R_fifo[sender] += 1
		# else reject
		return res

	# constructor (str pid, int maxServer, int[] delay_range)
	def __init__(self, pid, maxServer, delay_range):
		self.num_deliver = 0
		# self pid
		self.pid = pid
		# num of msg cur server has sent to group
		self.S_fifo = 0
		# seq num of latest group msg cur server has delievered from other server
		self.R_fifo = [0 for i in xrange(maxServer)]
		self.maxServer = maxServer
		# init unicast client
		self.node = unicast.Unicast(pid, maxServer, delay_range, self.recv)
		# hold-back queue
		self.hbQueue = []

class TotalMult:
	# basic multicast (str msg)
	def __basic(self, msg, pid = None):
		for idx in xrange(self.maxServer):
			if idx != pid:
				self.node.unicast_send(str(idx), msg)

	# deliever msg (int sender, str msg)
	def __deliever(self, sender, msg):
		self.num_deliver += 1
		if msg == 'bye':
			print "Listener is stopped, press ENTER to exit node."
			return True
		print "Receive \"%s\" from process %s with time %f" % ( msg, sender, time.time())
		return False

	# if current node is still listening
	def isUp(self):
		return self.node.isRunning()

	# total multicast msg (str msg)
	def send(self, msg):
		# piggyback flag and local identifier
		val = {'flag': 0, 'I': self.S_total, 'msg': msg}
		# increment R_total
		self.S_total += 1
		# basic multicast msg
		self.__basic(val)

	# recv method for sequencer (str pid, dict data)
	def __seqRecv(self, pid, data):
		print "Sequencer received msg from", pid
		if pid != self.pid:
			# construct msg
			msg = {'flag':1, 'S': self.S_total, 'pid':pid, 'msg': "seq", 'I':data['I']}
			# basic multicast msg
			self.__basic(msg, self.pid)
			# increment S_Total
			self.S_total += 1
			return data['msg'] == 'bye'
		return False

	# handle received msg (str pid, dict msg)
	def recv(self, pid, msg):
		def helper():
			# wait until S = r in hbQueue
			for i in xrange(len(self.seqs)):
				for data in self.seqs:
					seq, pid, I = data
					for val in self.hbQueue:
						sender, idx, msg = val
						# if msg with according sender and identifier is ready to deliever
						if idx == I and sender == pid and seq == self.R_total:
							# remove msg from both queues
							self.hbQueue.remove(val)
							self.seqs.remove(data)
							# deliever msg
							if self.__deliever(sender, msg):
								return True
							# increment R_total
							self.R_total = seq + 1
			return False
		# if current node is sequencer
		if self.pid == '0':
			return self.__seqRecv(pid, msg)
		else: # current node is not sequencer
			# if not from sequencer
			if msg['flag'] == 0:
				# add msg to hold-back queue
				self.hbQueue.append((pid, msg['I'], msg['msg']))
			else:
				# add sequencer msg to sequencer queue
				self.seqs.append((msg['S'], msg['pid'], msg['I']))
			# find matching msg in 2 queues and deliever
			return helper()
		return False

	# constructor (str pid, int maxServer, int[] delay_range)
	def __init__(self, pid, maxServer, delay_range):
		self.num_deliver = 0
		# self pid
		self.pid = pid
		# init local send counter
		self.S_total = 0
		if pid != '0': # if not sequencer
			# init group member recived counter
			self.R_total = 0
			# hold-back queue
			self.hbQueue = []
			# hold-back queue for sequencer
			self.seqs = []
		else:
			print "This node is sequencer, plz do NOT send msg from this node."
		# init unicast client
		self.maxServer = maxServer
		self.node = unicast.Unicast(pid, int(maxServer), delay_range, self.recv)

class CausalMult:
	# basic multicast (sre msg)
	def __basic(self, msg):
		for idx in xrange(self.maxServer):
			self.node.unicast_send(str(idx), msg)

	# deliever msg (int sender, str msg)
	def __deliever(self, sender, msg):
		if msg == 'bye':
			print "Listener is stopped, press ENTER to exit node."
			return True
		print "Receive \"%s\" from process %s with time %f" % ( msg, sender, time.time())
		self.num_deliver +=1
		return False

	# if current node is still listening
	def isUp(self):
		return self.node.isRunning()

	# causal multicast msg (str msg)
	def send(self,msg):
		# increment V[i] by 1
		self.V_causal[int(self.pid)] += 1
		# piggy back vector timestamp
		val = {'vec': self.V_causal, 'msg':msg}
		# basic multicast msg
		self.__basic(val)
	
	# handle received msg (str pid, dict msg)
	def recv(self, pid, msg):
		sender, vec, val = int(pid), msg['vec'], msg['msg']
		# place val in hold-back queue
		self.hbQueue.append((sender, vec, val))
		# loop through queue
		for i in range(len(self.hbQueue)):
			for val in self.hbQueue:
				sender, vec, msg = val
				# receivce msg from itself
				if sender == int (self.pid):
					#deliver the oldest msg
					if vec[sender] == self.deliver_own + 1:
						if self.__deliever(sender, msg):
							return True
						# remove msg from hold back queue
						self.hbQueue.remove(val)
						self.deliver_own +=1
				# receive msg from others
				elif vec[sender] == self.V_causal[sender] + 1: #make sure deliver myself
					flag = True
					for idx in xrange(self.maxServer):
						# if vec is newest (check all the slots except itself and the sender)
						if vec[idx] > self.V_causal[idx] and not (idx == sender):
							flag = False
							break
					if flag:
						# deliever msg
						if self.__deliever(sender, msg):
							return True
						# remove msg from hold back queue
						self.hbQueue.remove(val)
						# increment v[sender] if sender is not current node 
						self.V_causal[sender] += 1
		return False

	# constructor (str pid, int maxServer, int[] delay_range)
	def __init__(self, pid, maxServer, delay_range):
		#local clock to keep track of delivering own msg
		self.deliver_own = 0 
		self.num_deliver = 0
		# hold-back queue
		self.hbQueue = []
		# seld id
		self.pid = pid
		# init number of servers
		self.maxServer = maxServer
		# vector timestamp init
		self.V_causal = [0 for idx in xrange(maxServer)]
		# init unicast client
		self.node = unicast.Unicast(pid, maxServer, delay_range, self.recv)

# type of multicast nodes
mults = {'fifo':FifoMult, 'total':TotalMult, 'causal':CausalMult}
def Main():
	# get usr input for pid, order, maxServer
	pid, maxServer, order = sys.argv[1:4]
	delay_range = unicast.delay_range
	print "<<<<<<< chat room >>>>>>>>"
	# init multicast node
	node = mults[order](pid, int(maxServer), delay_range)
	#record the starting time
	system_time_start = time.time()
	while True:
		# take input
		userInput = raw_input()
		# stop if node is not listening
		if not node.isUp():
			#running time of this particular node
			print "process running time: %f s" % (time.time() - system_time_start)
			break
		# get msg
		_,msg = userInput.split(" ",1)
		# multicast msg
		node.send(msg)

if __name__ == "__main__":
	Main()