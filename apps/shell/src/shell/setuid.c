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

static int min_uid = 500;

int chown_delegation_token_files(char *delegation_token_files, int uid, int gid) {
  char *modifiable_delegation_token_files = strdup(delegation_token_files);
  if (modifiable_delegation_token_files == NULL) {
    fprintf(stderr, "Error: strdup returned NULL, system out of memory.\n");
    return -1;
  }

  char *delegation_token_file = strtok(modifiable_delegation_token_files, ",");
  while (delegation_token_file != NULL) {
    errno = 0;
    int chown_result = chown(delegation_token_file, uid, gid);
    if (chown_result == -1) {
      fprintf(stderr, "Could not change ownership of file \"%s\" to UID %d and GID %d\n", delegation_token_file, uid, gid);
      fprintf(stderr, "Errno %d : %s\n", errno, strerror(errno));
      free(modifiable_delegation_token_files);
      return -1;
    }
    delegation_token_file = strtok(NULL, ",");
  }
  free(modifiable_delegation_token_files);
  return 0;
}

int set_gid_uid(int gid, int uid) {
  gid_t group = gid;

  errno = 0;
  int result_of_step = setgroups(1, &group);
  if (result_of_step != 0) {
    fprintf(stderr, "Error: Could not set groups list to [%d]\n", gid);
    fprintf(stderr, "Errno %d: %s\n", errno, strerror(errno));
    return -1;
  }

  errno = 0;
  result_of_step = setregid(gid, gid);
  if (result_of_step != 0) {
    fprintf(stderr, "Error: Could not set real and effective group ID to %d\n", gid);
    fprintf(stderr, "Errno %d: %s\n", errno, strerror(errno));
    return -1;
  }

  errno = 0;
  result_of_step = setreuid(uid, uid);
  if (result_of_step != 0) {
    fprintf(stderr, "Error: Could not set real and effective user ID to %d\n", uid);
    fprintf(stderr, "Errno %d: %s\n", errno, strerror(errno));
    return -1;
  }

  return 0;
}

int main(int argc, char **argv) {
  
  if (argc < 4){
    fprintf(stderr, "Usage: setuid <desired user ID> <desired group ID> <executable> <arguments for executable>\n");
    return -1;
  }

  errno = 0;
  int uid = strtol(argv[1], (char **)NULL, 10);
  if (errno != 0) {
    fprintf(stderr, "Error: Invalid value for UID: \"%s\"\n", argv[1]);
    fprintf(stderr, "Errno %d: %s\n", errno, strerror(errno));
    return -1;
  }

  errno = 0;
  int gid = strtol(argv[2], (char **)NULL, 10);
  if (errno != 0) {
    fprintf(stderr, "Error: Invalid value for GID: \"%s\"\n", argv[2]);
    fprintf(stderr, "Errno %d: %s\n", errno, strerror(errno));
    return -1;
  }

  if (uid < min_uid) {
    fprintf(stderr, "Error: value %d for UID is less than the minimum UID allowed (%d)\n", uid, min_uid);
    return -1;
  }

  char *delegation_token_files = getenv("HADOOP_TOKEN_FILE_LOCATION");
  if (delegation_token_files != NULL) {
    int chown_result = chown_delegation_token_files(delegation_token_files, uid, gid);
    if (chown_result != 0) {
      fprintf(stderr, "Error: Could not change ownership of delegation token files, exiting.\n");
      return -1;
    }
  }

  int set_gid_uid_result = set_gid_uid(gid, uid);
  if (set_gid_uid_result != 0) {
    fprintf(stderr, "Error: Could not correctly change to running as correct user, exiting.\n");
    return -1;
  }

  int executable_index = 3;
  const char *executable = argv[executable_index];
  char **param_list = (char **) calloc(argc - executable_index + 1, sizeof(char *));
  int i;
  for (i = 0; i < argc - executable_index; i++) {
    param_list[i] = argv[executable_index + i];
  }

  int result = execvp(executable, param_list);

  fprintf(stderr, "An exec error occurred. The given command for the executable was \"%s\". Is this on the path?.\n", executable);
  fprintf(stderr, "Exec returned %d with errno %d: %s\n", result, errno, strerror(errno));
  return 0;
}

