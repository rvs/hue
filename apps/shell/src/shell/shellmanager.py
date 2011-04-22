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

import logging
LOG = logging.getLogger(__name__)

class NewShellInterrupt(Exception):
  def __init__(self, new_shell_pairs):
    self.new_shell_pairs = new_shell_pairs

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
      p = subprocess.Popen(shell_command, stdin=child, stdout=child, stderr=child,
                                                                 env=subprocess_env, close_fds=True)
    except (OSError, ValueError):
      os.close(parent)
      os.close(child)
      raise

    # State that shouldn't be touched by any other classes.
    self._output_buffer_length = 0
    self._commands = []
    self._fd = parent
    self._child_fd = child
    self.subprocess = p
    self.pid = p.pid
    self._write_buffer = cStringIO.StringIO()
    self._read_buffer = cStringIO.StringIO()

    # State that's accessed by other classes.
    self.shell_id = shell_id
    # Timestamp that is updated on shell creation and on every output request. Used so that we know
    # when to kill the shell.
    self.time_received = time.time()
    self.last_output_sent = False

  def kill(self):
    try:
      os.kill(self.subprocess.pid, signal.SIGKILL)
    except OSError, e:
      LOG.debug("Error calling kill on subprocess %d, might have exited already" % (self.subprocess.pid,))
    try:
      os.close(self._fd)
    except OSError, e:
      LOG.debug("Error closing file descriptor %d" % (self._fd,))
    try:
      os.close(self._child_fd)
    except OSError, e:
      LOG.debug("Error closing file descriptor %d" % (self._child_fd,))
    self._read_buffer.close()
    self._write_buffer.close()
    
  def get_previous_output(self):
    """
    Called when a Hue session is restored. Returns a tuple of ( all previous output, next offset).
    """
    val = self._read_buffer.getvalue()
    return ( val, len(val))

  def get_previous_commands(self):
    return self._commands

  def get_cached_output(self, offset):
    """
    The offset is not the latest one, so some output has already been generated and is
    stored in the read buffer. So let's fetch it from there.
    """
    self._read_buffer.seek(offset)
    next_output = self._read_buffer.read()
    if not next_output:
      return None
    more_available = len(next_output) >= constants.OS_READ_AMOUNT
    return (next_output, more_available, self._output_buffer_length)

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
    
    try:
      r, w, x = select.select([],[self._fd],[])
    except Exception, e:
      # The next 9 lines are taken from Facebook's Tornado project, which is open-sourced under
      # the Apache license.     
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
      bytes_written = os.write(self._fd, buffer_contents)
      self._advance_write_buffer(bytes_written)
    except OSError, e:
      if e.errno == errno.EINTR:
        return # TODO: Call spawn_n again?
      elif e.errno != errno.EAGAIN:
        format_str = "Encountered error while writing to process with PID %d:%s"
        LOG.error(format_str % (self.pid, e)) # TODO: What to do here?
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

  def read_child_output(self):
    """
    Reads up to constants.OS_READ_AMOUNT bytes from the child subprocess's stdout. Returns a tuple
    of (output, more_available). The second parameter indicates whether more output might be
    obtained by another call to read_child_output.
    """
    ofd = self._fd
    result = None
    try:
      next_output = os.read(ofd, constants.OS_READ_AMOUNT)
      self._read_buffer.seek(self._output_buffer_length)
      self._read_buffer.write(next_output)
      length = len(next_output)
      self._output_buffer_length += length
      num_excess_chars = self._output_buffer_length - shell.conf.SHELL_BUFFER_AMOUNT.get()
      if num_excess_chars > 0:
        self._read_buffer.seek(num_excess_chars)
        newval = self._read_buffer.read()
        self._read_buffer.truncate(0)
        self._read_buffer.write(newval)
    except OSError, e: # No more output at all
      if e.errno == errno.EINTR:
        pass
      elif e.errno != errno.EAGAIN:
        format_str = "Encountered error while reading from process with PID %d : %s"
        LOG.error( format_str % (self.subprocess.pid, e))
        # self.mark_for_cleanup() TODO: What to do here?
    else:
      more_available = length >= constants.OS_READ_AMOUNT
      result = (next_output, more_available, self._output_buffer_length)
    
    if not result:
      # TODO: What to do here?
      pass
    return result

class ShellManager(object):
  """
  The class that manages state for all shell subprocesses.
  """
  def __init__(self):
    self._shells = {} # Keys are (username, shell_id) tuples. Each user has his/her own set of shell ids.
    shell_types = [] # List of available shell types. For each shell type, we have a nice name (e.g. "Python Shell") and a short name (e.g. "python")
    self._command_by_short_name = {} # Map each short name to its command (e.g. ["pig", "-l", "/dev/null"])
    self._meta = {} # Map usernames to utils.UserMetadata objects
    self._greenlets_by_hid = {} # Map each Hue Instance ID (HID) to greenlets currently fetching output for that HID.
    self._hids_by_pid = {} # Map each process ID (PID) to the HID whose greenlet is currently doing a "select" on the process's output fd.
    self._greenlets_to_notify = {} # For each PID, maintain a set of greenlets who are also interested in the output from that process, but are not doing the select.
    self._shells_by_fds = {} # Map each file descriptor to the Shell instance whose output it represents.
    self._greenlet_interruptable = {}
    
    for item in shell.conf.SHELL_TYPES.keys():
      nice_name = shell.conf.SHELL_TYPES[item].nice_name.get()
      short_name = shell.conf.SHELL_TYPES[item].short_name.get()
      shell_types.append({ constants.NICE_NAME: nice_name, constants.KEY_NAME: short_name })
      command = shell.conf.SHELL_TYPES[item].command.get().split()
      self._command_by_short_name[short_name] = command

    self.shell_types_response = { constants.SUCCESS: True, constants.SHELL_TYPES: shell_types }
    # We will have to return this a lot so we violate MVC a little bit and store the JSON formatted
    # string instead of the dictionary.
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
    self._shells_by_fds[shell_instance._fd] = shell_instance
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
      # TODO: Clean up metadata for shell and user.
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
    return shell_instance.process_command(command)

  def _interrupt_with_output(self, readable):
    greenlets_set = set()
    for fd in readable:
      shell_instance = self._shells_by_fds.get(fd)
      if not shell_instance:
        LOG.error("Shell for readable file descriptor '%d' is missing" % (fd,))
      else:
        greenlets_to_notify = self._greenlets_to_notify.get(shell_instance.pid, [])
        greenlets_set.update(greenlets_to_notify)
    nsi = NewShellInterrupt([])
    for greenlet_to_notify in greenlets_set:
      if self._greenlet_interruptable.get(greenlet_to_notify):
        greenlet_to_notify.throw(nsi)

  def _read_helper(self, shell_instance, offset=None):
    if offset is not None:
      cache_read_result = shell_instance.get_cached_output(offset)
      if not cache_read_result:
        return None
      total_output, more_available, next_offset = cache_read_result
    else:
      total_output, more_available, next_offset = shell_instance.read_child_output()
    # If this is the last output from the shell, let's tell the JavaScript that.
    if shell_instance.subprocess.poll() is None:
      status = constants.ALIVE
    else:
      status = constants.EXITED
      shell_instance.last_output_sent = True
    return { status : True, constants.OUTPUT : total_output,
            constants.MORE_OUTPUT_AVAILABLE : more_available,
            constants.NEXT_OFFSET : next_offset }
 
  def retrieve_output(self, username, hue_instance_id, shell_pairs):
    """
    Called when an output request is received from the client. Sends the request to the appropriate
    shell instances.
    """
    
    time_received = time.time()
    total_cached_output = {}
    offsets_for_shells = {}
    current_greenlet = eventlet.getcurrent()
    self._greenlets_by_hid[hue_instance_id] = current_greenlet
    shell_pairs = set(shell_pairs)    

    result = None
    while (time.time() - time_received) < constants.BROWSER_REQUEST_TIMEOUT:
      for shell_id, offset in shell_pairs:
        shell_instance = self._shells.get((username, shell_id))
        if shell_instance:
          offsets_for_shells[shell_instance] = offset
          cached_output = self._read_helper(shell_instance, offset)
          if cached_output:
            total_cached_output[shell_id] = cached_output
        else:
          LOG.warn("User '%s' has no shell with ID '%s'" % (username, shell_id))
          total_cached_output[shell_id] = { constants.NO_SHELL_EXISTS: True }
      
      if total_cached_output:
        LOG.debug("Serving output request from cache")
        result = total_cached_output
        break
      
      fds_to_listen_for = []
      for shell_id, offset in shell_pairs:
        shell_instance = self._shells.get((username, shell_id))
        # Here we can assume shell_instance exists because if it didn't, we would have broken out of
        # the while loop above and we wouldn't be executing this code.
        listening_hid = self._hids_by_pid.get(shell_instance.pid)
        if listening_hid is not None and listening_hid != hue_instance_id:
          if not shell_instance.pid in self._greenlets_to_notify:
            self._greenlets_to_notify[shell_instance.pid] = set()
          self._greenlets_to_notify[shell_instance.pid].add(current_greenlet)
        else:
          fds_to_listen_for.append(shell_instance._fd)
          self._hids_by_pid[shell_instance.pid] = hue_instance_id
      
      try:
        time_remaining = constants.BROWSER_REQUEST_TIMEOUT - (time.time() - time_received)
        self._greenlet_interruptable[current_greenlet] = True
        readable, writable, exception_occurred = select.select(fds_to_listen_for, [], [], time_remaining)
        self._greenlet_interruptable[current_greenlet] = False
      except NewShellInterrupt, nsi:
        self._greenlet_interruptable[current_greenlet] = False
        # Here, I'm assuming that we won't have a situation where one of the (shell_id, offset)
        # tuples in nsi.new_shell_pairs has the same shell_id as an item in shell_pairs, but
        # an offset with a different (has to be higher) number.
        shell_pairs.update(nsi.new_shell_pairs)  
      else:
        if not readable:
          result = { constants.PERIODIC_RESPONSE: True }
        else:
          result = {}
          for fd in readable:
            shell_instance = self._shells_by_fds.get(fd)
            if not shell_instance:
              LOG.error("Shell for readable file descriptor '%d' is missing" % (fd,))
            else:
              result[shell_instance.shell_id] = self._read_helper(shell_instance)
          eventlet.spawn_n(self._interrupt_with_output, readable)
          break
    
    if not result:
      result = { constants.PERIODIC_RESPONSE: True }
    
    self._greenlets_by_hid.pop(hue_instance_id)
    for shell_id, offset in shell_pairs:
      shell_instance = self._shells.get((username, shell_id))
      if shell_instance:
        if self._hids_by_pid.get(shell_instance.pid) == hue_instance_id:
          self._hids_by_pid.pop(shell_instance.pid)
        else:
          try:
            self._greenlets_to_notify[shell_instance.pid].remove(current_greenlet)
          except KeyError:
            LOG.error("Greenlet for pid %d was not found in set of listening greenlets" % (shell_instance.pid,))
    return result
  
  def add_to_output(self, username, hue_instance_id, shell_pairs):
    """
    Adds the given shell_id, offset pairs to the output connection associated with the given Hue
    instance ID.
    """
    def interrupt(green_let, message):
      green_let.throw(message)
    new_shells_interrupt = NewShellInterrupt(shell_pairs)
    greenlet_for_hid = self._greenlets_by_hid.get(hue_instance_id)
    if greenlet_for_hid:
      eventlet.spawn_n(interrupt, greenlet_for_hid, new_shells_interrupt) 
    return { constants.SUCCESS : True }
  
