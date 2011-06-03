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
from hadoop.cluster import all_mrclusters, get_all_hdfs
import pty
import pwd
import shell.conf
import shell.constants as constants
import shell.utils as utils
from eventlet.green import os
from eventlet.green import select
import signal
import simplejson
import subprocess
import tempfile
from eventlet.green import time
import sys

import logging
LOG = logging.getLogger(__name__)

class NewShellInterrupt(Exception):
  def __init__(self, new_shell_pairs):
    self.new_shell_pairs = new_shell_pairs

class Shell(object):
  """
  A class to encapsulate I/O with a shell subprocess.
  """
  def __init__(self, shell_command, shell_id, username, delegation_token_dir):
    subprocess_env = {}
    env = desktop.lib.i18n.make_utf8_env()
    for item in constants.PRESERVED_ENVIRONMENT_VARIABLES:
      value = env.get(item)
      if value:
        subprocess_env[item] = value

    parent, child = pty.openpty()

    user_info = pwd.getpwnam(username)
    path_to_setuid = "%s/setuid" % (os.path.dirname(__file__),)
    subprocess_env[constants.HOME] = user_info.pw_dir
    command_to_use = [path_to_setuid, '%d' % (user_info.pw_uid,), '%d' % (user_info.pw_gid,)]
    command_to_use.extend(shell_command)

    delegation_token_files = self._get_delegation_tokens(username, delegation_token_dir)
    if delegation_token_files:
      subprocess_env[constants.HADOOP_TOKEN_FILE_LOCATION] = ','.join([token_file.name for token_file in delegation_token_files])

    try:
      p = subprocess.Popen(command_to_use, stdin=child, stdout=child, stderr=child,
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
    self._delegation_token_files = delegation_token_files

    # State that's accessed by other classes.
    self.shell_id = shell_id
    # Timestamp that is updated on shell creation and on every output request. Used so that we know
    # when to kill the shell.
    self.time_received = time.time()
    self.last_output_sent = False
    self.remove_at_next_iteration = False
    self.destroyed = False

  def _get_delegation_tokens(self, username, delegation_token_dir):
    delegation_token_files = []
    all_clusters = []
    all_clusters += all_mrclusters().values()
    all_clusters += get_all_hdfs().values()

    LOG.info("all_clusters: %s" % (repr(all_clusters),))

    for cluster in all_clusters:
      if cluster.security_enabled:
        current_user = cluster.user
        cluster.setuser(username)
        token = cluster.get_delegation_token()
        token_file = tempfile.NamedTemporaryFile(dir=delegation_token_dir)
        token_file.write(token.delegationTokenBytes)
        token_file.flush()
        delegation_token_files.append(token_file)
        cluster.setuser(current_user)

    return delegation_token_files

  def mark_for_cleanup(self):
    self.remove_at_next_iteration = True

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
    more_available = len(next_output) >= shell.conf.SHELL_OS_READ_AMOUNT.get()
    return (next_output, more_available, self._output_buffer_length)

  def process_command(self, command):
    LOG.debug("Command received for pid %d : '%s'" % (self.pid, command,))
    if len(self._write_buffer.getvalue()) >= shell.conf.SHELL_WRITE_BUFFER_LIMIT.get():
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
    self._write_buffer.write("%s" % (command,))
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
        eventlet.spawn_n(self._write_child_when_able)
      else:
        LOG.error("Unexpected error on select")
        self.mark_for_cleanup()
      return

    if not w:
      return

    try:
      bytes_written = os.write(self._fd, buffer_contents)
      self._advance_write_buffer(bytes_written)
    except OSError, e:
      if e.errno == errno.EINTR:
        eventlet.spawn_n(self._write_child_when_able)
      elif e.errno != errno.EAGAIN:
        format_str = "Encountered error while writing to process with PID %d:%s"
        LOG.error(format_str % (self.pid, e))
        self.mark_for_cleanup()
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
    Reads up to conf.SHELL_OS_READ_AMOUNT bytes from the child subprocess's stdout. Returns a tuple
    of (output, more_available). The second parameter indicates whether more output might be
    obtained by another call to read_child_output.
    """
    ofd = self._fd
    result = None
    try:
      next_output = os.read(ofd, shell.conf.SHELL_OS_READ_AMOUNT.get())
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
        self.mark_for_cleanup()
    else:
      more_available = length >= shell.conf.SHELL_OS_READ_AMOUNT.get()
      result = (next_output, more_available, self._output_buffer_length)
    
    return result
  
  def destroy(self):
    try:
      for delegation_token_file in self._delegation_token_files:
        delegation_token_file.close()
      self._delegation_token_files = None
      self._write_buffer.close()
      self._read_buffer.close()

      os.close(self._fd)
      os.close(self._child_fd)

      try:
        LOG.debug("Sending SIGKILL to process with PID %d" % (self.subprocess.pid,))
        os.kill(self.subprocess.pid, signal.SIGKILL)
        # We could try figure out which exit statuses are fine and which ones are errors.
        # But that would be difficult to do correctly since os.wait might block.
      except OSError:
        pass # This means the subprocess was already killed, which happens if the command was "quit"
    finally:
      self.destroyed = True

class ShellManager(object):
  """
  The class that manages state for all shell subprocesses.
  """
  def __init__(self):
    self._shells = {} # Keys are (username, shell_id) tuples. Each user has his/her own set of shell ids.
    shell_types = [] # List of available shell types. For each shell type, we have a nice name (e.g. "Python Shell") and a short name (e.g. "python")
    self._command_by_short_name = {} # Map each short name to its command (e.g. ["pig", "-l", "/dev/null"])
    self._meta = {} # Map usernames to utils.UserMetadata objects
    self._greenlets_by_hid = {} # Map each Hue Instance ID (HID) to greenlet currently fetching output for that HID.
    self._hids_by_pid = {} # Map each process ID (PID) to the HID whose greenlet is currently doing a "select" on the process's output fd.
    self._greenlets_to_notify = {} # For each PID, maintain a set of greenlets who are also interested in the output from that process, but are not doing the select.
    self._shells_by_fds = {} # Map each file descriptor to the Shell instance whose output it represents.
    self._greenlet_interruptable = {} # For each greenlet, store if it can be safely interrupted.

    self._delegation_token_dir = shell.conf.SHELL_DELEGATION_TOKEN_DIR.get()
    if not os.path.exists(self._delegation_token_dir):
      os.mkdir(self._delegation_token_dir)
    
    for item in shell.conf.SHELL_TYPES.keys():
      nice_name = shell.conf.SHELL_TYPES[item].nice_name.get()
      short_name = shell.conf.SHELL_TYPES[item].short_name.get()
      shell_types.append({ constants.NICE_NAME: nice_name, constants.KEY_NAME: short_name })
      command = shell.conf.SHELL_TYPES[item].command.get().split()
      self._command_by_short_name[short_name] = command
    
    self.shell_types = shell_types
    eventlet.spawn_after(1, self._handle_periodic)

  @classmethod
  def global_instance(cls):
    if not hasattr(cls, "_global_instance"):
      cls._global_instance = cls()
    return cls._global_instance

  def available_shell_types(self, user):
    username = user.username
    try:
      user_info = pwd.getpwnam(username)
    except KeyError:
      user_info = None
    if not user_info:
      return { constants.NO_SUCH_USER: True }
    
    shell_types_for_user = [item for item in self.shell_types if user.has_desktop_permission('launch_%s' % (item[constants.KEY_NAME],),'shell')]
    return { constants.SUCCESS: True, constants.SHELL_TYPES: shell_types_for_user }

  def _interrupt_conditionally(self, green_let, message):
    if self._greenlet_interruptable.get(green_let):
      green_let.throw(message)

  def _cleanup_greenlets_for_removed_pids(self, removed_pids):
    greenlets_to_cleanup = set()
    for pid in removed_pids:
      listening_hid = self._hids_by_pid.get(pid)
      if listening_hid:
        greenlet_for_hid = self._greenlets_by_hid.get(listening_hid)
        if greenlet_for_hid:
          greenlets_to_cleanup.add(greenlet_for_hid)
      non_selecting_greenlets = self._greenlets_to_notify.get(pid)
      if non_selecting_greenlets:
        greenlets_to_cleanup.update(non_selecting_greenlets)
    nsi = NewShellInterrupt([])
    for greenlet_to_notify in greenlets_to_cleanup:
      eventlet.spawn_n(self._interrupt_conditionally, greenlet_to_notify, nsi)

  def _handle_periodic(self):
    """
    Called every second. Kills shells which haven't been asked about in conf.SHELL_TIMEOUT
    seconds (currently 600).
    """
    try:
      keys_to_pop = []
      current_time = time.time()
      for key, shell_instance in self._shells.iteritems():
        if shell_instance.last_output_sent or shell_instance.remove_at_next_iteration:
          keys_to_pop.append(key)
        elif shell_instance.subprocess.poll() is not None:
          keys_to_pop.append(key)
        else:
          difftime = current_time - shell_instance.time_received
          if difftime >= shell.conf.SHELL_TIMEOUT.get():
            keys_to_pop.append(key)
      removed_pids = [self._shells.get(key).pid for key in keys_to_pop]
      for key in keys_to_pop:
        self._cleanup_shell(key)
    finally:
      eventlet.spawn_n(self._cleanup_greenlets_for_removed_pids, removed_pids)
      eventlet.spawn_after(1, self._handle_periodic)


  def _cleanup_shell(self, key):
    shell_instance = self._shells[key]
    shell_instance.destroy()
    self._shells.pop(key)
    username = key[0]
    self._meta[username].decrement_count()
    self._shells_by_fds.pop(shell_instance._fd)

  def try_create(self, user, key_name):
    """
    Attemps to create a new shell subprocess for the given user. Writes the appropriate failure or
    success response to the client.
    """
    command = self._command_by_short_name.get(key_name)
    if not command:
      return { constants.SHELL_CREATE_FAILED : True }

    username = user.username
    try:
      user_info = pwd.getpwnam(username)
    except KeyError:
      return { constants.NO_SUCH_USER : True }

    if not user.has_desktop_permission('launch_%s' % (key_name,), 'shell'):
      return { constants.SHELL_NOT_ALLOWED : True }

    if not username in self._meta:
      self._meta[username] = utils.UserMetadata(username)

    user_metadata = self._meta[username]
    shell_id = user_metadata.get_next_id()
    try:
      LOG.debug("Trying to create a shell for user %s" % (username,))
      shell_instance = Shell(command, shell_id, username, self._delegation_token_dir)
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
      shell_instance.mark_for_cleanup()
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
    shell_instance.time_received = time.time()
    output, next_offset = shell_instance.get_previous_output()
    commands = shell_instance.get_previous_commands()
    return { constants.SUCCESS: True, constants.OUTPUT: output, constants.NEXT_OFFSET: next_offset,
      constants.COMMANDS: commands}

  def process_command(self, username, shell_id, command):
    shell_instance = self._shells.get((username, shell_id))
    if not shell_instance:
      return { constants.NO_SHELL_EXISTS : True }
    shell_instance.time_received = time.time()
    command += "\n" # TODO: Tab completion
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
      eventlet.spawn_n(self._interrupt_conditionally, greenlet_to_notify, nsi)

  def _read_helper(self, shell_instance, offset=None):
    if offset is not None:
      read_result = shell_instance.get_cached_output(offset)
    else:
      read_result = shell_instance.read_child_output()
    if not read_result:
      return None
    total_output, more_available, next_offset = read_result
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
    
    for shell_id, offset in shell_pairs:
      shell_instance = self._shells.get((username, shell_id))
      if shell_instance:
        shell_instance.time_received = time_received

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
      shell_instances_for_listened_fds = {}
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
          shell_instances_for_listened_fds[shell_instance._fd] = shell_instance
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
            shell_instance = shell_instances_for_listened_fds[fd]
            if shell_instance.destroyed:
              result[shell_instance.shell_id] = { constants.SHELL_KILLED : True }
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
    new_shells_interrupt = NewShellInterrupt(shell_pairs)
    greenlet_for_hid = self._greenlets_by_hid.get(hue_instance_id)
    if greenlet_for_hid:
      eventlet.spawn_n(self._interrupt_conditionally, greenlet_for_hid, new_shells_interrupt) 
    return { constants.SUCCESS : True }
