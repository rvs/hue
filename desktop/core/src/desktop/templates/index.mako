## Licensed to Cloudera, Inc. under one
## or more contributor license agreements.  See the NOTICE file
## distributed with this work for additional information
## regarding copyright ownership.  Cloudera, Inc. licenses this file
## to you under the Apache License, Version 2.0 (the
## "License"); you may not use this file except in compliance
## with the License.  You may obtain a copy of the License at
##
##     http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"> 
<html>
<head>
  <meta http-equiv="X-UA-Compatible" content="IE=8" />
  <title>Hue</title>
  <link rel="shortcut icon" href="/static/art/favicon_solid.png" type="image/x-icon" /> 
  <link rel="icon" href="/static/art/favicon_solid.png" type="image/x-icon" />
  <link rel="stylesheet" href="/static/css/shared.css" type="text/css" media="screen" title="no title" charset="utf-8">
  <link rel="stylesheet" href="/static/css/reset.css" type="text/css" media="screen" charset="utf-8">
  <link rel="stylesheet" href="/static/css/windows.css" type="text/css" media="screen" charset="utf-8">
  <link rel="stylesheet" href="/static/css/desktop.css" type="text/css" media="screen" charset="utf-8">

  <script src="/depender/build?client=true&require=dbug,DomReady,Cookie,Element.Dimensions,Element.Style,ART.Menu,Cookie"></script>
  <!--[if IE 8]>
      <script>
          window.ie8 = true;
      </script>
  <![endif]-->
  <script>
  
  window.addEvent('domready', function(){
    //this method automatically sizes the desktop image to fill the screen
    var sizer = function(){
      //get the backgrounds (there may be more than one if rotation is in process)
      var bgs = $('bg').getElements('.desktop-bg');
      //get the window dimensions
      var size = window.getSize();
      //if the aspect ratio of the window is > 1.6
      if (size.x/size.y > 1.6) {
        //then set the width of the image to equal the window
        bgs.setStyles({
          width: size.x,
          height: 'auto'
        });
      } else {
        //else set the height to match the window
        bgs.setStyles({
          width: 'auto',
          height: size.y
        });
      }
    };
    //when the window is resized, resize the background
    window.addEvent('resize', sizer);
    
    if (Browser.Engine.trident) {
      //if we're in IE, there's a note about the fact that Hue doesn't love IE
      //add a click handler for hiding this note.
      $('closeWarning').addEvent('click', function(){
        //store the preference
        Cookie.write('desktop-browser-warned', true);
        //remove the class (which hides the warning)
        $(document.body).removeClass('warned');
      });
      if (!Cookie.read('desktop-browser-warned')) $(document.body).addClass('warned');
      if (!ie8) alert("Hue does not currently support any version of Internet Explorer other than IE8.");
    }
    var appName = "Hue";
    Depender.require({
      scripts: ["CCS.Request", "CCS.User", "CCS.Desktop", "CCS.Desktop.Config", "CCS.Desktop.FlashMessage", 
        "CCS.Desktop.Keys", "CCS.Login", "StickyWin.PointyTip", "Element.Delegation", "Fx.Tween", "Fx.Elements"],
      callback: function(){
        //before fading in the screen, resize the background to match the window size
        sizer();
        //get the background images
        var bgEls = $('bg').getElements('img');
        //include the background container
        bgEls.push($('bg'));
        var styles = {};
        //loop through each and create an effect that fades them from 0 to 1 opacity
        bgEls.each(function(el, i){
          styles[i.toString()] = { opacity: [0, 1] };
        });
        //fade them in
        new Fx.Elements(bgEls, {
          duration: 500
        }).start(styles);
        //when the user clicks the hue logo, rotate the background
        $(document.body).addEvent('click:relay(img.desktop-logo)', rotateBG);
        
        //configure the clientcide assets location.
        Clientcide.setAssetLocation("/static/js/ThirdParty/clientcide/Assets");
        var growled = {};
        //add a notification for when apps are launched
        var launchGrowl = function(component){
          //get the app name ("File Browser" from "filebrowser")
          var appName = CCS.Desktop.getAppName(component);
          //show the appropriate flash message; if it's loaded then we're just "launching"
          //else show "loading"
          var loading = 'Loading ' + appName;
          var launching = 'Launching ' + appName;
          var msg = loading;
          if (CCS.Desktop.hasLoaded(component)) msg = launching;
          if (!CCS.Desktop.checkForFlashMessage(loading) && 
              !CCS.Desktop.checkForFlashMessage(launching) && 
              !$$('.loadingmsg').length) {
                growled[component] = CCS.Desktop.flashMessage(msg, 10000);
          }
        };
        var clearGrowl = function(component) {
          if (growled[component]) {
            growled[component]();
            delete growled[component];
          }
        };
        CCS.Desktop.initialize({
          onBeforeLoad: launchGrowl,
          onBeforeLaunch: launchGrowl,
          onAfterLaunch: clearGrowl
        });
        //fade out the ccs-loading message
        (function(){
          $('ccs-loading').fade('out').get('tween').clearChain().chain(function(){
            $('ccs-loading').destroy();
          });
        }).delay(300);

        //when the user logs in
        CCS.User.withUser(function(user){
          var bsLoaded;
          //this method runs once the bootstrap is run and the apps are registered
          var bootstrapped = function(){
            //ensure it only runs once
            if (bsLoaded) return;
            bsLoaded = true;

            //if there's no desktop to restore
            var linked = CCS.Desktop.launchLinked();
            // If a link was opened it chooses how to restore the desktop
            var restored;

            //we need to delay this slightly for IE; don't ask me why
            var finalize = function(){
              if (!linked) {
                //this is how we hide things in IE because it hates opacity/visibility stuff w/ VML
                $('ccs-desktop').setStyle('top', -10000);
                restored = CCS.Desktop.restoreDesktop();
                $('ccs-desktop').setStyle('top', null);
              }
              if (!linked && !restored) {
                //call the autolaunchers
                CCS.Desktop.autolaunchers.each(function(fn){
                  fn();
                });
              }
              //display the user as logged in
              $('ccs-profileLink').set('text', user.username).addClass('loggedIn');
              $(document.body).addClass('ccs-loaded');
              window.scrollTo(0,0);
              //fade in the toolbar
              $('ccs-toolbar').show().tween('opacity', 0, 1);
              //and the dock
              $('ccs-dock').tween('opacity', 0, 1);
            };

            //IE needs a brief delay
            if (Browser.Engine.trident) finalize.delay(100);
            else finalize();
          };

          //load the bootstraps
          new Element('script', {
            src: '/bootstrap.js',
            events: {
              //on load call the bootstrapped method above
              load: function() {
                bootstrapped();
              },
              //IE requires you monitor the readystate yourself for script tags
              readystatechange: function(){
                if (['loaded', 'complete'].contains(this.readyState)) bootstrapped();
              }
            }
          }).inject(document.head);
        });

      }
    });
  });
  </script>

  <script>
    % if send_dbug_messages:
      window.sendDbug = true;
    % else:
      window.sendDbug = false;
    % endif
  </script>
</head>
<body>
  <ul id="desktop-menu" class="desktop-menu" style="position:absolute; top: -100000px;">
  </ul>
  <div id="bg">
    <script>
      (function(){
        /*
          this array is the "pretty name" list of background images.
          in theory, this could be a json definition on the back end...
          
          At the moment, these correspond to images in /static/art/desktops by index,
          so "Pencil Tips" below maps to 1.jpg. Clunky, I know.
          
          Also, because the logos are color matched (their hue is changed to match, get it?),
          there has to be a corresponding 1.logo.jpg in the same directory.
        */
        var bgNames = [
          'Pencil Tips',
          'Color Pencils',
          'Pencil Tips2',
          'Painted Wood',
          'Purple Flower',
          'Pantone Cards',
          'Blue Windows',
          'Tree Frog',
          'Red Wood',
          'Hadoop!',
          'Fuzzy Sparkles',
          'Green Leaves',
          'Pastels'
        ];
        //and these are static colors
        var bgColors = {
          'Solid Grey': '#444',
          'Rich Blue': '#2f6390',
          'Grey Green': '#5F7D5F',
          'Khaki': '#E0DCAD'
        };
        //get the user's previous choice which we stored in a cookie
        var pref = Cookie.read('bgPref'),
            r;
        //if they have a pref and it's one of the images, use that
        if (pref && bgNames.contains(pref)) r = bgNames.indexOf(pref);
        //otherwise pick a random one
        else r = $random(1, bgNames.length);
        //inject a random background
        document.write('<img src="/static/art/desktops/' + r + '.jpg" class="desktop-bg"><img src="/static/art/desktops/' + r + '.logo.png" class="desktop-logo">');
        //if they have a pref and it's a static color, hide the image
        //and set the background color
        if (pref && bgColors[pref]) {
          $$('.desktop-bg')[0].setStyle('opacity', 0);
          $('bg').setStyle('background-color', bgColors[pref]);
        }
        //background rotation function
        this.rotateBG = function(filename){
          //grab the images there now
          var bg = $('bg').getElement('.desktop-bg');
          var logo = $('bg').getElement('.desktop-logo');
          //if a filename was specified, use it
          if (filename) {
            r = filename;
          } else {
            //otherwise use the index
            //because the file names are not zero-indexed
            //add 1
            if (r < bgNames.length) r++;
            else r = 1; 
          }
          //inject the image and icon
          new Element('img', {
            src: '/static/art/desktops/' + r + '.logo.png',
            'class': 'desktop-logo'
          }).inject($('bg'), 'top');
          new Element('img', {
            src: '/static/art/desktops/' + r + '.jpg',
            'class': 'desktop-bg',
            styles: bg.getStyles('width', 'height'),
            events: {
              load: function(){
                //after they load, crossfade
                new Fx.Elements([bg, logo], {duration: 500}).start({
                  '0': {
                    'opacity': 0
                  },
                  '1': {
                    'opacity': 0
                  }
                }).chain(function(){
                  bg.destroy();
                  logo.destroy();
                });
              }
            }
          }).inject($('bg'), 'top');
        };
        //now we create the menu
        //first we list all the names
        bgNames.each(function(name, i){
          new Element('li', {
            'class': 'menu-item'
          }).inject('desktop-menu').adopt(
            new Element('a', {
              html: name,
              'class': i == r ? 'current' : ''
            })
          );
        });
        //a separator
        new Element('li', {
          'class': 'menu-separator'
        }).inject('desktop-menu');
        //and then all the static colors
        for (name in bgColors){
          new Element('li', {
            'class': 'menu-item'
          }).inject('desktop-menu').adopt(
            new Element('a', {
              html: name,
              'data-bgcolor': bgColors[name],
              'class': name == pref ? 'current' : ''
            })
          );
        }
        //finally, we create a new instance of ART.Menu for the background container
        Depender.require({
          scripts: ["ART.Menu"],
          callback: function(){
            ART.Sheet.define('menu.art.desktop-menu', {
              'z-index': 10002
            });
            
            var menu = new ART.Menu({
              className: 'art desktop-menu',
              startEvent: 'contextmenu',
              tabIndex: 10,
              onPress: function(link){
                //when an item is chosen
                var links = $('desktop-menu').getElements('a');
                //remove the current flag from which everone is current
                links.removeClass('current');
                //get the index of the new one
                var index = links.indexOf(link);
                //if the index is < the names list length, cross fade the image
                if (index < bgNames.length) {
                  rotateBG(index + 1);
                  Cookie.write('bgPref', index);
                } else {
                // else we hide the image and set the background color to the static color
                  Cookie.write('bgPref', link.get('html'));
                  $('bg').tween('background-color', link.get('data-bgcolor'));
                  var bg = $$('.desktop-bg')[0];
                  bg.tween('opacity', 0).get('tween').chain(function(){
                    bg.setStyle('visibility', 'visible');
                  });
                }
                link.addClass('current');
              }
            }, $('desktop-menu'), $('bg')).inject($('ccs-desktop'));
          }
        });
      })();
    </script>
  </div>
  <div id="browserWarn">Hue is best experienced in <a target="browsers" href="http://getfirefox.com">Mozilla Firefox</a>, <a target="browsers" href="http://www.apple.com/safari/">Apple Safari</a>, or <a target="browsers" href="http://www.google.com/chrome">Google Chrome</a> <a id="closeWarning"></a></div>
  <div id="ccs-desktop" class="ccs-shared">
    <div id="ccs-topnav">
      <div id="ccs-toolbar">
        <img src="/static/art/favicon.png" width="16" height="16" class="ccs-swoosh">
        <span>
          Hi
          <span id="ccs-profileLink"></span>

          <span id="ccs-logout">
            [<a href="/accounts/logout">logout</a>]
          </span>
        </span>
        <a id="hotkeys" title="show keyboard shortcuts">
          <img src="/static/art/shortcut.png"> Shortcuts
        </a>
      </div>
    </div>
    <div id="ccs-dock">
      <div id="ccs-dock-content">
        <div id="ccs-dock-status" class="ccs-inline">
          <div id="ccs-dock-status-content">
          </div>
        </div>
        <span id="ccs-dock-icons">
        </span>
      </div>
    </div>
    <div id="ccs-loading">Launching Hue</div>
    <a id="ccs-feedback" href="${feedback_url}" target="_blank"><img src="/static/art/feedback-tab.png" width="76" height="26"/></a>
  </div>
  <div class="alert_popup ccs-error-popup">
    Warning, an AJAX request was made for the Hue desktop which cannot be loaded into an application window. Typically this means that a link clicked has no <em>href</em> value. Please notify the application's author.
  </div>

    <script>
      if (Browser.Engine.trident) $(document.body).addClass('IEroot');
      $(document.body).addClass(Browser.Engine.name);
    </script>
</body>
</html>
