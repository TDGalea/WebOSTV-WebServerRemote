#!/usr/bin/env python

# WebOS Python 2.7 Web Server by TDGalea
# Capable of hosting any HTML file with support for /multiple/paths.
# Also intended as a web-based remote.
#
# Makes use of custom Bash scripts expected to be at /home/root/.bin - all available at the same GitHub repo.
#
# Do what you want with this script - I just ask that you keep my original credit.

import ast
import mimetypes
import os
import socket
import struct
import subprocess
import sys
import time
import urllib

### VIRTUAL REMOTE SETUP ###

EVENT_FORMAT = 'llHHi'
EV_KEY = 1
EV_SYN = 0
SYN_REPORT = 0

# Change path if you wish - you might have to edit the keycodes to match your TV.
keysfile = '/home/root/webserver/keycodes.list'
with open(keysfile, 'r') as c:
	KEYCODES = ast.literal_eval(c.read())

def emit(fd, etype, code, value):
	t = time.time()
	sec = int(t)
	usec = int((t - sec) * 1e6)
	fd.write(struct.pack(EVENT_FORMAT, sec, usec, etype, code, value))
	fd.flush()

def press(keycode):
	with open('/dev/input/event1', 'wb') as fd:
		emit(fd, EV_KEY, keycode, 1)
		emit(fd, EV_SYN, SYN_REPORT, 0)
		emit(fd, EV_KEY, keycode, 0)
		emit(fd, EV_SYN, SYN_REPORT, 0)

### WEB SERVER SETUP ###

CTYPE = "\r\nContent-Type: text/html\r\n\r\n"

# Change this if you want - or remove it. Whatever.
HTML = """<!DOCTYPE HTML>
<head>
	<style>
		body {
			background-color: black;
			color: white;
			font-size: 32px;
		}
	</style>
</head>
<body>
	<center>
"""

# This file is intended as an easy way to add commands. Again, change or remove if you desire.
cmdfile = '/home/root/webserver/commands.list'
if os.path.isfile(cmdfile):
	with open(cmdfile, 'r') as c:
		COMMANDS = ast.literal_eval(c.read())

# Where are you keeping your HTML files?
DOC_ROOT = '/home/root/webserver/html'

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 80))
s.listen(5)

print 'Server up'
try:
	subprocess.check_output(['/home/root/.bin/notify', 'Web server running.'])
except Exception:
	pass

while True:
	conn, addr = s.accept()
	data = conn.recv(1024)
	path = data.split(' ')[1] if len(data.split(' ')) > 1 else '/'
	filepath = DOC_ROOT + path	

	# Remote functionality - intended to be /key/KEYCODE
	if path in KEYCODES:
		key = KEYCODES[path]
		press(key)

	# External commands file - whatever path you choose, but I'd recommend /cmd/COMMAND
	if path in COMMANDS:
		try:
			out = subprocess.check_output(COMMANDS[path])
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + out)
		except:
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + 'Command error: ' + path) 
			print 'Command error: ' + path

	# Standard webserver functionality - if the folder exists and has an index.html, serve it.
	elif os.path.isdir(filepath):
		filepath = filepath.rstrip('/') + '/index.html'
		if os.path.isfile(filepath):
			mime = mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
			with open(filepath, 'rb') as f:
				content = f.read()
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + content)

	# This path will exit this script. Intended to be re-spawned by an external keepalive.
	elif path == '/cmd/webserver/stop':
		conn.sendall('HTTP/1.1 200 OK' + CTYPE + HTML + 'Webserver exiting.')
		conn.close()
		s.close()
		quit()

	# App launcher - for example, /app/jellyfin
	# Relies on my fuzzy-search app launcher Bash script.
	elif path.startswith('/app/'):
		appname = path[5:]
		try:
			out = subprocess.check_output(['/home/root/.bin/app-onscreen', 'launch', appname])
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + out)
		except:
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + 'App launch error: ' + appname)
			print 'App launch error: ' + appname

	# Backlight control - relies on my backlight Bash script.
	elif path.startswith('/backlight/'):
		blAction = path[11:]
		if blAction.startswith('get'):
			out = subprocess.check_output(['/home/root/.bin/backlight', 'plain', 'get'])
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + out)
		elif blAction.startswith('set'):
			newBl = blAction[4:]
			try:
				out = subprocess.check_output(['/home/root/.bin/backlight', 'plain', 'set', newBl])
				conn.sendall('HTTP/1.1 200 OK' + CTYPE + out)
			except:
				conn.sendall('HTTP/1.1 200 OK' + CTYPE + 'Backlight set error.')
				print 'Backlight set error.'

	# Volume control - relies on my volume Bash script.
	elif path.startswith('/vol/'):
		volAction = path[5:]
		if volAction.startswith('get'):
			out = subprocess.check_output(['/home/root/.bin/volume', 'plain', 'get'])
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + out)
		elif volAction.startswith('set'):
			newVol = volAction[4:]
			try:
				out = subprocess.check_output(['/home/root/.bin/volume', 'plain', 'set', newVol])
				conn.sendall('HTTP/1.1 200 OK' + CTYPE + out)
			except:
				conn.sendall('HTTP/1.1 200 OK' + CTYPE + 'Volume set error.')
				print 'Volume set error.'
		else:
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + 'Invalid volume command.')

	# Text input - relies on my text input Bash script.
	elif path.startswith('/text/'):
		text = urllib.unquote(path[6:])
		try:
			out = subprocess.check_output(['/home/root/.bin/text', text])
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + 'Text received: ' + text)
		except:
			conn.sendall('HTTP/1.1 200 OK' + CTYPE + 'Text error: ' + text)
			print ' Text error: ' + text

	# Explains itself.
	else:
		conn.sendall('HTTP/1.1 404 Not Found\r\n\r\nInvalid page or command.')

	conn.close()
