#!/usr/bin/env python
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

# TODO: Green appropriate imports

from desktop.lib.django_util import render
from django.http import HttpResponse
import datetime
from eventlet.green import time
import simplejson
import shell.conf
import shell.constants as constants
from shell.shellmanager import ShellManager

def index(request):
  return render('index.mako', request, dict(date=datetime.datetime.now()))

def shell_types(request):
  shell_manager = ShellManager.global_instance()
  return HttpResponse(shell_manager.shell_types_response, mimetype="application/json")

def create(request):
  shell_manager = ShellManager.global_instance()
  username = request.user.username
  key_name = request.POST.get(constants.KEY_NAME, "")
  result = shell_manager.try_create(username, key_name)
  return HttpResponse(simplejson.dumps(result), mimetype="application/json")

def kill_shell(request):
  shell_manager = ShellManager.global_instance()
  username = request.user.username
  shell_id = request.POST.get(constants.SHELL_ID, "")
  result = shell_manager.kill_shell(username, shell_id)
  return HttpResponse(result)

def restore_shell(request):
  shell_manager = ShellManager.global_instance()
  username = request.user.username
  shell_id = request.POST.get(constants.SHELL_ID, "")
  result = shell_manager.get_previous_output(username, shell_id)
  return HttpResponse(simplejson.dumps(result), mimetype="application/json")

def process_command(request):
  shell_manager = ShellManager.global_instance()
  username = request.user.username
  shell_id = request.POST.get(constants.SHELL_ID, "")
  command = request.POST.get(constants.COMMAND, "")
  result = shell_manager.process_command(username, shell_id, command)
  return HttpResponse(simplejson.dumps(result), mimetype="application/json")

def retrieve_output(request):
  shell_manager = ShellManager.global_instance()
  username = request.user.username
  hue_instance_id = request.META.get(constants.HUE_INSTANCE_ID, "")
  shell_pairs = utils.parse_shell_pairs(request)
  result = shell_manager.retrieve_output(username, hue_instance_id, shell_pairs)
