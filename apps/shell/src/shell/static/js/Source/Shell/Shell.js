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

script: Shell.js

description: Defines Shell; a Hue application that extends Hue.JBrowser.

authors:
- Aditya Acharya

requires: [JFrame/JFrame.Browser, hue-shared/Hue.Request, Core/Element, Core/Native]
provides: [Shell]

...
*/
ART.Sheet.define('window.art.browser.shell', {
	'min-width': 620
});

(function(){
  var expressions = [
    {
      expr: /&/gm,
      replacement: '&amp;'
    },
    {
      expr: /</gm,
      replacement: '&lt;'
    },
    {
      expr: />/gm,
      replacement: '&gt;'
    },
    {
      expr: /"/gm,
      replacement: '&quot;'
    },
    {
      expr: /\n/g,
      replacement: "<br>"
    }
  ];

  String.implement({
    escapeHTML: function(){
      var cleaned = this;
      expressions.each(function(expression) {
        cleaned = cleaned.replace(expression.expr, expression.replacement);
      });
      return cleaned;
    }
  });
})();

var Shell = new Class({

	Extends: Hue.JBrowser,
	options: {
		className: 'art browser logo_header shell',
		displayHistory: false
	},

	initialize: function(path, options){
		this.parent(path || '/shell/', options);
		if(options && options.shellId){
			this.shellId = options.shellId;
		}
		this.addEvent("load", this.startShell.bind(this));
	},

	startShell: function(view){
		// Set up some state shared between "fresh" and "restored" shells.
		this.previousCommands = new Array();
		this.currentCommandIndex = -1;

		this.jframe.markForCleanup(this.cleanUp.bind(this));
		this.shellKilled = false;

		this.background = $(this).getElement('.jframe_contents');
		this.background.setStyle("background-color", "#ffffff");
		this.container = $(this).getElement('.jframe_padded');
		this.output = new Element('span', {
			'class':'fixed_width_font'
		});
		this.input = new Element('textarea', {
			'class':'fixed_width_font'
		});
		this.button = new Element('input', {
			type:'button',
			value:'Send command',
			'class':'ccs-hidden'
		});
	
		this.jframe.scroller.setOptions({
			duration: 200
		});
	
		// The command-sending request.  We can reuse this repeatedly to send commands
		// to the subprocess running on the server.
		this.commandReq = new Request.JSON({
			method: 'post',
			url: '/shell/process_command'
		});
	
		// Now let's kick off the appropriate thing, either a new shell or a restore.
		if(this.shellId){
			// TODO: Shell restoration
			this.startRestore(view);
		}else{
			this.setup(view);
		}
	},
	
	setup: function(view){
		this.shellCreated = false;
		this.shellTypesReq = new Request.JSON({
			method: 'get',
			url: '/shell/shell_types',
			onSuccess: this.shellTypesReqCompleted.bind(this),
			onFailure: this.shellTypesReqFailed.bind(this)
		});
		this.shellTypesReq.send();
	},

	buildSelectionMenu: function(shellTypes){
		this.background.setStyle("background-color", "#aaaaaa");
		var table = new Element("table");		
		this.container.empty();		
		this.container.grab(table);
		var maxWidth = 0;
		var tds = new Array();
		for(var i = 0; i < shellTypes.length; i++){
			var tr = new Element("tr");
			var td = new Element("td", {
				'class':'round Button',
				html: shellTypes[i].niceName.escapeHTML()
			});
			tr.grab(td);
			table.grab(tr);
			var tdWidth = parseInt(td.getStyle("width")) + parseInt(td.getStyle("padding-left")) + parseInt(td.getStyle("padding-right"));
			maxWidth = tdWidth > maxWidth ? tdWidth : maxWidth;
			tds.push(td);
		}
		for(var i = 0; i < tds.length; i++){
			tds[i].setStyle("width", maxWidth);
		}
	},

	shellTypesReqCompleted: function(json, text){
		this.shellTypesReq = null;
		if(json.success){
			this.buildSelectionMenu(json.shellTypes);
		}else{
			//What if it doesn't work?
		}
	},

	shellTypesReqFailed: function(){
		this.shellTypesReq = null;
		this.errorMesage("Error", "Could not retrieve available shell types.");
	},

	cleanUp: function(){
		if(this.shellTypesReq){
			this.shellTypesReq.cancel();
		}
		if(this.registerReq){
			this.registerReq.cancel();
		}
		if(this.restoreReq){
			this.restoreReq.cancel();
		}
		if(this.commandReq){
			this.commandReq.cancel();
		}

		var shellId = this.shellId;
		this.options.shellId = null;
		this.shellId = null;

		if(shellId){
			//TODO
			//Hue.ShellPoller.stopListening(shellId);
			var req = new Request.JSON({
				method: 'post',
				url: '/shell/kill_shell'
			});
			req.send({
				data: 'shellId=' + shellId
			});
		}
	}
});
