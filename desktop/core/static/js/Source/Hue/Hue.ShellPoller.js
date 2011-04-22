// Licensed to Cloudera, Inc. under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  Cloudera, Inc. licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
/*
---
description: I/O functionality shared between instances of the Shell app.
provides: [Hue.ShellPoller]
requires: [Hue.Request]
script: Hue.ShellPoller.js

...
*/

var hueInstanceID = function(){
    var chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXTZabcdefghiklmnopqrstuvwxyz";
    var lastIndex = chars.length - 1;
    var stringLength = 128;
	var randomString = "";
	for (var i = 0; i < stringLength; i++){
	    var randomIndex = $random(0, lastIndex);
	    randomString += chars.substring(randomIndex, randomIndex+1);
	}
	return randomString;
}();

Request.implement({
	options: {
		headers: {
		    "Hue-Instance-ID" : hueInstanceID
		}
	}
});


Hue.ShellPoller = {
  initialize: function(){
    this.outputReq = new Request.JSON({
      method: 'post',
      url: '/shell/retrieve_output',
      onSuccess: this.outputReceived.bind(this),
      onFailure: this.outputRequestFailed.bind(this)
    });
    this.addToOutputReq = new Request.JSON({
      method: 'post',
      url: '/shell/add_to_output',
      onSuccess: this.addToOutputCompleted.bind(this),
      onFailure: this.addToOutputFailed.bind(this)
    });
    this.numAdditionalReqsSent = 0;
    this.additionalReqs = new Array();
    this.addToOutputReqOpen = false;
    this.requestOpen = false;
    this.initialized = true;
    this.requestsStopped = true;
    this.dispatchInfo = {};
    this.backoffTime = 1;
  },

  listenForShell: function(shellId, offset, callback){
      // One-time initialization
      if(!this.initialized){
        this.initialize();
      }

      // Register the dispatch information for this shell ID.
      this.dispatchInfo[shellId] = {callback:callback, offset:offset};

      // If an output request is already open, use the secondary channel to add the new shell and
      // offset to the existing output request.
      if(this.requestOpen){
          this.addToOutputChannel(shellId, offset);
      }
      
      // We might be between openOutputChannel calls, so check to see if we've stopped
      // the requests or if we're just in between calls. If we've stopped, restart them.
      if(this.requestsStopped){
          this.requestsStopped = false;
          this.openOutputChannel();          
      }
  },
  
  // Remove the dispatch info for the given shell id. We don't have to do a request.cancel() since
  // either there's only 1 shell and we won't reissue once the request completes, or there are 
  // multiple and we might want to reissue.
  stopShellListener: function(shellId){
      this.dispatchInfo[shellId] = null;
  },
  
  // Convert the information stored in this.dispatchInfo into the form that the backend speaks.
  serializeShellData: function(){
      var serializedShells = new Array();
      var numShells = 0;
      for(var shellId in this.dispatchInfo){
          var shellInfo = this.dispatchInfo[shellId];
          if(shellInfo){
              numShells++;
              serializedShells.push("shellId"+numShells+"="+shellId);
              serializedShells.push("offset"+numShells+"="+shellInfo.offset);
          }
      }
      serializedShells.push("numPairs="+numShells);
      return serializedShells.join("&");
  },
  
  openOutputChannel: function(){
      this.requestOpen = true;
      var serializedData = this.serializeShellData();
      this.outputReq.send({ data: serializedData });
  },

  outputRequestFailed: function(){
      this.requestOpen = false;
      setTimeout(this.openOutputChannel.bind(this), this.backoffTime);
      this.backoffTime *= 2;
  },
  
  outputReceived: function(json, text){
      this.requestOpen = false;
      this.backoffTime = 1;

      var closeOutputChannel = true; // Used to determine if we should issue a new output request.
      if(json.periodicResponse){
          closeOutputChannel = false; // If it's just a "keep-alive", we should reissue.
      }
      
      for(var shellId in json){
          var shellInfo = this.dispatchInfo[shellId];
          if(shellInfo){
              var result = json[shellId];
              if(result.alive || result.exited){
                  shellInfo.offset = result.nextOffset;
                  if(!(result.alive || result.moreOutputAvailable)){
                      this.stopShellListener(shellId);
                  }
              }else{
                  this.stopShellListener(shellId);
              }
              shellInfo.callback(result);
          }
          
          // Now let's check if we still care about this shell. If not, we'll have called
          // stopShellListener on it and this.dispatchInfo[shellId] will be null.
          if(this.dispatchInfo[shellId]){ 
              closeOutputChannel = false; // We care still, so let's reissue an output req.
          }
      }

      if(closeOutputChannel){
          //None of the shells in the response are still listening. Check to see if any other is.
          for(var shellId in this.dispatchInfo){
              if(this.dispatchInfo[shellId]){
                  closeOutputChannel = false; // >=1 shells are listening, so let's reissue
              }
          }
      }

      if(!closeOutputChannel){
          //can't use openOutputChannel.delay(0, this) here because it causes buggy behavior in Firefox.
          setTimeout(this.openOutputChannel.bind(this), 0);
      }else{
          // Let's set this flag to true so that we can reopen the channel on the next listener.
          this.requestsStopped = true;
      }
  },
  
  addToOutputChannel: function(shellId, offset){
      // First let's store the info
      this.additionalReqs.push({shellId: shellId, offset: offset});
      this.sendAdditionalReq();
  },
  
  serializeAdditionalReqs: function(){
      // Convert the additional things we need to register into our output channel into the
      // same format as used for output requests.
      var serializedData = new Array();
      for(var i = 0; i < this.additionalReqs.length; i++){
          serializedData.push("shellId"+(i+1)+"="+this.additionalReqs[i].shellId+
                              "&offset"+(i+1)+"="+this.additionalReqs[i].offset);
      }
      serializedData.push("numPairs="+this.additionalReqs.length);
      return serializedData.join("&");
  },
  
  sendAdditionalReq: function(){
      this.addToOutputReqOpen = true;
      var serializedData = this.serializeAdditionalReqs();
      this.numAdditionalReqsSent = this.additionalReqs.length;
      this.addToOutputReq.send({ data: serializedData });
  },
  
  addToOutputCompleted: function(json, text){
      this.backoffTime = 1;
      this.addToOutputReqOpen = false;
      if(json.success){
          this.additionalReqs.splice(0, this.numAdditionalReqsSent);
          this.numAdditionalReqsSent = 0;
          if(this.additionalReqs.length){
              this.sendAdditionalReq.delay(0, this);
	      setTimeout(this.sendAdditionalReq.bind(this), 0);
          }
      }else if(json.restartHue){
          alert("Your version of Hue is not up to date. Please restart your browser.");
      }else{
          this.numAdditionalReqsSent = 0;
          setTimeout(this.sendAdditionalReq.bind(this), 0);
      }
  },
  
  addToOutputFailed: function(){
      this.addToOutputReqOpen = false;
      this.numAdditionalReqsSent = 0;
      setTimeout(this.sendAdditionalReq.bind(this), this.backoffTime);
      this.backoffTime *= 2;
  }
};
