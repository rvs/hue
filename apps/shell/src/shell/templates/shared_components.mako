<%!
import datetime
from django.template.defaultfilters import urlencode, escape
%>
<%def name="header(title='Hue Shell', toolbar=True, shells=[])">
  <!DOCTYPE html>
  <html>
    <head>
      <title>${title}</title>
    </head>
    <body>
      <div class="toolbar">
        <a href="${url('shell.views.index')}"><img src="/shell/static/art/shell.png" class="shell_icon"/></a>
        % if toolbar:
          <div class="nav_menu">
          % if len(shells) == 1:
            <a target="Shell" class="nav_button Button round" href="${url('shell.views.create')}?keyName=${shells[0]["keyName"]}">${shells[0]["niceName"]}</a>
          % else:
            <a target="Shell" class="nav_button Button roundLeft" href="${url('shell.views.create')}?keyName=${shells[0]["keyName"]}">${shells[0]["niceName"]}</a>
            % for item in shells[1:-1]:
              <a target="Shell" class="nav_button Button" href="${url('shell.views.create')}?keyName=${item["keyName"]}">${item["niceName"]}</a>
            % endfor
            <a target="Shell" class="nav_button Button roundRight" href="${url('shell.views.create')}?keyName=${shells[-1]["keyName"]}">${shells[-1]["niceName"]}</a>
          % endif
          </div>
        % endif
      </div>
</%def>

<%def name="footer()">
    </body>
  </html>
</%def>
