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

from desktop.lib.django_util import render
from django.http import HttpResponse
import datetime
from eventlet.green import time
import simplejson
import shell.conf
import shell.constants as constants

_cached_shell_types = []
for item in shell.conf.SHELL_TYPES.keys():
  nice_name = shell.conf.SHELL_TYPES[item].nice_name.get()
  short_name = shell.conf.SHELL_TYPES[item].short_name.get()
  _cached_shell_types.append({ constants.NICE_NAME: nice_name,
                                      constants.KEY_NAME: short_name })
_cached_shell_types_response = simplejson.encoder.JSONEncoder().encode({ constants.SUCCESS : True,
                                                 constants.SHELL_TYPES : _cached_shell_types })
def index(request):
  return render('index.mako', request, dict(date=datetime.datetime.now()))

def shell_types(request):
  return HttpResponse(_cached_shell_types_response)

def process_command(request):
  return HttpResponse(simplejson.encoder.JSONEncoder().encode({ constants.SUCCESS : True }))

def create(request):
  return HttpResponse(simplejson.encoder.JSONEncoder().encode({ constants.SUCCESS : True, constants.SHELL_ID : 1}))

def kill_shell(request):
  return HttpResponse("Shell killed")

def retrieve_output(request):
  time.sleep(12)
  return HttpResponse(simplejson.encoder.JSONEncoder().encode({ 1 : { constants.ALIVE : True,  constants.OUTPUT : "Some arbitrary output\n"} }))

def restore_shell(request):
  return HttpResponse(simplejson.encoder.JSONEncoder().encode({ constants.SUCCESS: False }))
