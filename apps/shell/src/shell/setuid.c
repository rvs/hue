/*
 Licensed to Cloudera, Inc. under one
 or more contributor license agreements.  See the NOTICE file
 distributed with this work for additional information
 regarding copyright ownership.  Cloudera, Inc. licenses this file
 to you under the Apache License, Version 2.0 (the
 "License"); you may not use this file except in compliance
 with the License.  You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
*/

#include <errno.h>
#include <grp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if(argc >= 4){
    int uid = strtol(argv[1], (char **)NULL, 10);
    int gid = strtol(argv[2], (char **)NULL, 10);
    if(!uid){
      fprintf(stderr, "Error: Invalid value for UID: \"%s\"\n", argv[1]);
      exit(-1);
    }
    if(!gid){
      fprintf(stderr, "Error: Invalid value for GID: \"%s\"\n", argv[2]);
      exit(-1);
    }
 
    char *delegation_token_files = getenv("HADOOP_TOKEN_FILE_LOCATION");
    if(delegation_token_files){
      delegation_token_files = strdup(delegation_token_files);
      if(delegation_token_files == NULL){
        fprintf(stderr, "Error: strdup returned NULL, system out of memory. Exiting.\n");
        exit(-1);
      }
      char *delegation_token_file = strtok(delegation_token_files, ",");
      while(delegation_token_file != NULL){
        chown(delegation_token_file, uid, gid);
        delegation_token_file = strtok(NULL, ",");
      }
    }

    gid_t group = gid;
    setgroups(1, &group);
    setregid(gid, gid);
    setreuid(uid, uid);

    int executable_index = 3;
    const char *executable = argv[executable_index];
    char **const param_list = calloc(argc - executable_index + 1, sizeof(char *));
    int i;
    for(i=0; i < argc - executable_index; i++){
      param_list[i] = argv[executable_index + i];
    }
    int result = execvp(executable, param_list);
    fprintf(stderr, "An execv error occurred. The given command for the executable was \"%s\". Is this on the path?.\n", executable);
    fprintf(stderr, "The error code was: %d, errno was %d\n", result, errno);
  }else{
    fprintf(stderr, "Usage: setuid <desired user ID> <desired group ID> <executable> <arguments for executable>\n");
  }
  return 0;
}

