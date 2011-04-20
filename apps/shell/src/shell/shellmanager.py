# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This module handles I/O with shells.  Much of the functionality has been pushed down into the
Shell class itself, but a lot also happens in ShellManager.
"""

# TODO: Green appropriate imports

import cStringIO
import eventlet
import desktop.lib.i18n
import pty
import shell.conf
import shell.constants as constants
import shell.utils as utils
from eventlet.green import os
from eventlet.green import select
import signal
import simplejson
import subprocess
from eventlet.green import time
import tty

import logging
LOG = logging.getLogger(__name__)

class Shell(object):
  """
  A class to encapsulate I/O with a shell subprocess.
  """
  def __init__(self, shell_command, shell_id):
    subprocess_env = {}
    env = desktop.lib.i18n.make_utf8_env()
    for item in constants.PRESERVED_ENVIRONMENT_VARIABLES:
      value = env.get(item)
      if value:
        subprocess_env[item] = value

    parent, child = pty.openpty()
    try:
      tty.setraw(parent)
    except tty.error:
      LOG.debug("Could not set parent fd to raw mode, user will see echoed input.")
    
    try:
      p = subprocess.Popen(shell_command, stdin=child, stdout=child, stderr=child,
                                                                 env=subprocess_env, close_fds=True)
    except (OSError, ValueError):
      os.close(parent)
      os.close(child)
      raise

    # State that isn't touched by any other classes.
    self._output_buffer_length = 0
    self._commands = []
    self._fd = parent
    self._child_fd = child
    self._subprocess = p
    self.pid = p.pid
    self._write_buffer = cStringIO.StringIO()
    self._read_buffer = cStringIO.StringIO()

    # State that's accessed by other classes.
    self.shell_id = shell_id
    # Timestamp that is updated on shell creation and on every output request. Used so that we know
    # when to kill the shell.
    self.time_received = time.time()

  def kill(self):
    try:
      os.kill(self._subprocess.pid, signal.SIGKILL)
    except OSError, e:
      LOG.debug("Error calling kill on subprocess %d, might have exited already" % (self._subprocess.pid,))
    try:
      os.close(self._fd)
    except OSError, e:
      LOG.debug("Error closing file descriptor %d" % (self._fd,))
    try:
      os.close(self._child_fd)
    except OSError, e:
      LOG.debug("Error closing file descriptor %d" % (self._child_fd,))

  def get_previous_output(self):
    """
    Called when a Hue session is restored. Returns a tuple of ( all previous output, next offset).
    """
    val = self._read_buffer.getvalue()
    return ( val, len(val))

  def get_previous_commands(self):
    return self._commands

  def process_command(self, command):
    LOG.debug("Command received for pid %d : '%s'" % (self.pid, command,))
    if len(self._write_buffer.getvalue()) >= constants.WRITE_BUFFER_LIMIT:
      LOG.debug("Write buffer too full, dropping command")
      return { constants.BUFFER_EXCEEDED : True }
    else:
      LOG.debug("Write buffer has room. Adding command to end of write buffer.")
      self._append_to_write_buffer(command)
      eventlet.spawn_n(self._write_child_when_able)
      return { constants.SUCCESS : True }

  def _append_to_write_buffer(self, command):
    """
    Append the received command, with an extra newline, to the write buffer. This buffer is used
    when the child becomes readable to send commands to the child subprocess.
    """
    self._write_buffer.seek(len(self._write_buffer.getvalue()))
    self._write_buffer.write("%s\n" % (command,))
    self._write_buffer.seek(0)
    self._commands.append(command)
    while len(self._commands) > 25:
      self._commands.pop(0)

  def _read_from_write_buffer(self):
    """
    Read and return the contents of the write buffer.
    """
    contents = self._write_buffer.read()
    self._write_buffer.seek(0)
    return contents

  def _write_child_when_able(self):
    LOG.debug("write_child_when_able")
    buffer_contents = self._read_from_write_buffer()
    if not buffer_contents:
      return
    
    fd = self._fd
    try:
      r, w, x = select.select([],[fd],[])
    except Exception, e:
      # Depending on python version and poll implementation,
      # different exception types may be thrown and there are
      # two ways EINTR might be signaled:
      # * e.errno == errno.EINTR
      # * e.args is like (errno.EINTR, 'Interrupted system call')
      if (getattr(e, 'errno') == errno.EINTR or
          (isinstance(getattr(e, 'args'), tuple) and
           len(e.args) == 2 and e.args[0] == errno.EINTR)):
        LOG.warning("Interrupted system call", exc_info=1)
      else:
        LOG.error("Unexpected error on select")
      return # TODO: Figure out what to do here. Call spawn_n again?

    if not w:
      return

    try:
      bytes_written = os.write(fd, buffer_contents)
      self._advance_write_buffer(bytes_written)
    except OSError, e:
      if e.errno == errno.EINTR:
        return # TODO: Call spawn_n again?
      elif e.errno != errno.EAGAIN:
        format_str = "Encountered error while writing to process with PID %d:%s"
        LOG.error(format_str % (self.pid, e))
    else: # This else clause is on the try/except above, not the if/elif
      if bytes_written != len(buffer_contents):
        eventlet.spawn_n(self._write_child_when_able)

  def _advance_write_buffer(self, num_bytes):
    """
    Advance the current position in the write buffer by num_bytes bytes.
    """
    # TODO: Replace this system with a list of cStringIO objects so that
    # it's more efficient. We should do this if this seems to be copying
    # a lot of memory around.
    self._write_buffer.seek(num_bytes)
    new_value = self._write_buffer.read()
    self._write_buffer.truncate(0)
    self._write_buffer.write(new_value)
    self._write_buffer.seek(0)

class ShellManager(object):
  """
  The class that manages state for all shell subprocesses.
  """
  def __init__(self):
    self._shells = {}
    self._shell_types = []
    self._command_by_short_name = {}
    self._meta = {}
    for item in shell.conf.SHELL_TYPES.keys():
      nice_name = shell.conf.SHELL_TYPES[item].nice_name.get()
      short_name = shell.conf.SHELL_TYPES[item].short_name.get()
      self._shell_types.append({ constants.NICE_NAME: nice_name,
                                constants.KEY_NAME: short_name })
      command = shell.conf.SHELL_TYPES[item].command.get().split()
      self._command_by_short_name[short_name] = command

    self.shell_types_response = { constants.SUCCESS: True, constants.SHELL_TYPES: self._shell_types }
    # We will have to do this a lot so we violate MVC a little bit and store the JSON formatted string instead
    # of the dictionary.
    self.shell_types_response = simplejson.dumps(self.shell_types_response)

  @classmethod
  def global_instance(cls):
    if not hasattr(cls, "_global_instance"):
      cls._global_instance = cls()
    return cls._global_instance

  def try_create(self, username, key_name):
    """
    Attemps to create a new shell subprocess for the given user. Writes the appropriate failure or
    success response to the client.
    """
    command = self._command_by_short_name.get(key_name)
    if not command:
      return { constants.SHELL_CREATE_FAILED : True }

    if not username in self._meta:
      self._meta[username] = utils.UserMetadata(username)
    user_metadata = self._meta[username]
    shell_id = user_metadata.get_next_id()
    try:
      LOG.debug("Trying to create a shell for user %s" % (username,))
      shell_instance = Shell(command, shell_id)
    except (OSError, ValueError), exc:
      LOG.error("Could not create shell : %s" % (exc,))
      return { constants.SHELL_CREATE_FAILED : True }

    LOG.debug("Shell successfully created")
    user_metadata.increment_count()
    self._shells[(username, shell_id)] = shell_instance
    return { constants.SUCCESS : True, constants.SHELL_ID : shell_id }

  def kill_shell(self, username, shell_id):
    """
    Called when the user closes the Shell app instance in Hue. Kills the subprocess.
    """
    shell_instance = self._shells.get((username, shell_id))
    if not shell_instance:
      response = "User '%s' has no shell with ID '%s'" % (username, shell_id)
    else:
      shell_instance.kill()
      response = "Shell successfully killed"
    LOG.debug(response)
    return response

  def get_previous_output(self, username, shell_id):
    """
    Called when the Hue session is restored. Get the outputs that we have previously written out to
    the client as one big string.
    """
    shell_instance = self._shells.get((username, shell_id))
    if not shell_instance:
      return { constants.SHELL_KILLED : True }
    output, next_offset = shell_instance.get_previous_output()
    commands = shell_instance.get_previous_commands()
    return { constants.SUCCESS: True, constants.OUTPUT: output, constants.NEXT_OFFSET: next_offset,
      constants.COMMANDS: commands}

  def process_command(self, username, shell_id, command):
    shell_instance = self._shells.get((username, shell_id))
    if not shell_instance:
      return { constants.NO_SHELL_EXISTS : True }
    result = shell_instance.process_command(command)

  def retrieve_output(self, username, hue_instance_id, shell_pairs):
    """
    Called when an output request is received from the client. Sends the request to the appropriate
    shell instances.
    """
    total_cached_output = {}
    for shell_id, offset in shell_pairs:
      shell_instance = self._shells.get((username, shell_id))
      if shell_instance:
        cached_output = shell_instance.get_cached_output(hue_instance_id, offset) # TODO: Write this method
        if cached_output:
          total_cached_output[shell_id] = cached_output
      else:
        LOG.warn("User '%s' has no shell with ID '%s'" % (username, shell_id))
        total_cached_output[shell_id] = { constants.NO_SHELL_EXISTS: True }

    if total_cached_output:
      LOG.debug("Serving output request from cache")
      return total_cached_output

    # If a previous greenlet exists for this HID:
    #   Cancel it

    # Register this greenlet as listening for this HID

    # For each shell_id in shell_pairs:
    #   If another HID is listening for that shell
    #     Register this greenlet as interested in that shell
    #   Else
    #     Add that shell to the list of shells we'll be listening for

    # Try:
    #    If we will be listening:
    #       select with a 50 second timeout
    #    Else:
    #       time.sleep(50)
    # Except ShellInterrupt s:
    #    # One of the processes we were interested in has output, it's shell_id is specified by s.shell_id
    #    Result = Read from cache
    # Else:
    #    If select timed out:
    #       Result = keep alive
    #    Else:
    #       # Holy shit we have output
    #       For each shell we listened for that had output:
    #           Read some amount of output.
    #           Update cache
    #       For each shell we listened for that had output:
    #           s = ShellException(shell_id)
    #           For each greenlet registered for the shell:
    #               Interrupt it with s
    # Finally:
    #   For all shells we were on the hook for:
    #     Unregister ourselves
  
    # Return result
