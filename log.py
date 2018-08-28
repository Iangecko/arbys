# Custom logging module for the bot because I don't like Python's built in logging module.
# Why I don't like it is not for a comment line in a file, though, so ask me if you want to know why.

import traceback
import time
import sys
import config
from datetime import datetime


logfile = "logs/" + time.strftime("%Y-%m-") + config.logfile
logfile_encoding = config.logfile_encoding


def now():
	return datetime.utcnow().__str__()


def debug(message: str, include_exception: bool = False) -> None:
	try:
		timestamp = now()
		if include_exception and (sys.exc_info()[2] is not None):
			message += "\n"+traceback.format_exc()
		if config.file_loglevel >= 5:
			with open(logfile, "a", encoding=logfile_encoding) as lf:
				lf.write(f"[{timestamp}] [D] {message}\n")
		if config.terminal_loglevel >= 5:
			sys.stdout.write(f"[{timestamp}] [D] {message}\n")
			sys.stdout.flush()
	except:
		# There are some cases that we could end up having a problem writing out logged information.
		# It's once happened to me where PyCharm crashed but disconnected my running bots, causing the stdio pipes to
		# break and any stdio failed, returning an exception back to Discord for every single message the bot received.
		# This is obviously *kinda* bad, but in reality the only cause for a broken pipe or a unwritable logfile is
		# because of user error, so if the user broke the log system it's their fault. We tried, but you screwed up and
		# we have no way to tell you, so we're simply going to ignore the log messages. You're on your own without them
		# because it's your fault. Sorry.
		pass


def info(message: str, include_exception: bool = False) -> None:
	try:
		timestamp = now()
		if include_exception and (sys.exc_info()[2] is not None):
			message += "\n"+traceback.format_exc()
		if config.file_loglevel >= 4:
			with open(logfile, "a", encoding=logfile_encoding) as lf:
				lf.write(f"[{timestamp}] [I] {message}\n")
		if config.terminal_loglevel >= 4:
			sys.stdout.write(f"[{timestamp}] [I] {message}\n")
			sys.stdout.flush()
	except:
		# See comment in debug() function here
		pass


def warn(message: str, include_exception: bool = False) -> None:
	try:
		timestamp = now()
		if include_exception and (sys.exc_info()[2] is not None):
			message += "\n"+traceback.format_exc()
		if config.file_loglevel >= 3:
			with open(logfile, "a", encoding=logfile_encoding) as lf:
				lf.write(f"[{timestamp}] [W] {message}\n")
		if config.terminal_loglevel >= 3:
			if config.exc_to_stderr:
				sys.stderr.write(f"[{timestamp}] [W] {message}\n")
				sys.stderr.flush()
			else:
				sys.stdout.write(f"[{timestamp}] [W] {message}\n")
				sys.stdout.flush()
	except:
		# See comment in debug() function here
		pass


warning = warn


def error(message: str, include_exception: bool = True) -> None:
	try:
		timestamp = now()
		if include_exception and (sys.exc_info()[2] is not None):
			message += "\n"+traceback.format_exc()
		if config.file_loglevel >= 2:
			with open(logfile, "a", encoding=logfile_encoding) as lf:
				lf.write(f"[[{timestamp}]] [E] {message}\n")
		if config.terminal_loglevel >= 2:
			if config.exc_to_stderr:
				sys.stderr.write(f"[{timestamp}] [E] {message}\n")
				sys.stderr.flush()
			else:
				sys.stdout.write(f"[[{timestamp}]] [E] {message}\n")
				sys.stdout.flush()
	except:
		# See comment in debug() function here
		pass


def critical(message: str, include_exception: bool = True) -> None:
	try:
		timestamp = now()
		if include_exception and (sys.exc_info()[2] is not None):
			message += "\n"+traceback.format_exc()
		if config.file_loglevel >= 1:
			with open(logfile, "a", encoding=logfile_encoding) as lf:
				lf.write(f"[{timestamp}] [C] {message}\n")
		if config.terminal_loglevel >= 1:
			if config.exc_to_stderr:
				sys.stderr.write(f"[{timestamp}] [C] {message}\n")
				sys.stderr.flush()
			else:
				sys.stdout.write(f"[{timestamp}] [C] {message}\n")
				sys.stdout.flush()
	except:
		# See comment in debug() function here
		pass


crit = critical


def fatal(message: str, include_exception: bool = True) -> None:
	try:
		timestamp = now()
		if include_exception and (sys.exc_info()[2] is not None):
			message += "\n"+traceback.format_exc()
		if config.file_loglevel >= 0:
			with open(logfile, "a", encoding=logfile_encoding) as lf:
				lf.write(f"[{timestamp}] [F] {message}\n")
		if config.terminal_loglevel >= 0:
			if config.exc_to_stderr:
				sys.stderr.write(f"[{timestamp}] [F] {message}\n")
				sys.stderr.flush()
			else:
				sys.stdout.write(f"[{timestamp}] [F] {message}\n")
				sys.stdout.flush()
	except:
		# See comment in debug() function here
		pass
