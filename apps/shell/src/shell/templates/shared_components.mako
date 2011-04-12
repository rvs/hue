<%!
#declare imports here, for example:
#import datetime
%>

<%!
import datetime
from django.template.defaultfilters import urlencode, escape
%>
<%def name="header(title='Hue Shell', toolbar=True)">
  <!DOCTYPE html>
  <html>
    <head>
      <title>${title}</title>
    </head>
    <body>
      % if toolbar:
      <div class="toolbar">
        <a href="${url('shell.views.index')}"><img src="/shell/static/art/shell.png" class="shell_icon"/></a>
	<a target="Shell" class="Button"><div class="plus_button"></div>New Window</a>
      </div>
      % endif
</%def>

<%def name="footer()">
    </body>
  </html>
</%def>
