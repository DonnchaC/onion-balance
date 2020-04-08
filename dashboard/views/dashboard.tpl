<html>
  <head>
    <meta http-equiv="refresh" content="3">
    <title>ob dash</title>
    <link href="data:image/x-icon;base64,AAABAAEAEBAQAAEABAAoAQAAFgAAACgAAAAQAAAAIAAAAAEABAAAAAAAgAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAA////AFZ4XgBsun4AvvfMAJfoqgArLC4AouuzADJUOgBz0YkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzMzMzAAAAA5kiIpkwAAA5kkREKZMAADlCSIQkkwAAOZREREmTAAA5k2RGOZMAAAOZNVM5MAAAADmVU5MAAAAAA5k3MAAAAAAAM3MAAAAAAAA3MAAAAAARE3MAAAAAARATMAAAAAABAAAAAAAAAAEAAAAAAAAAAAAAAAAAAADwDwAA4AcAAMADAADAAwAAwAMAAMADAADgBwAA8A8AAPgfAAD8PwAA/H8AAMD/AACR/wAAv/8AAL//AAD//wAA" rel="icon" type="image/x-icon" />
    <style>
      html {
        background-color: #fffefa;
        color: #303030;
      }
      #header {
        text-align: center;
      }
      #msg {
        border: 1px solid #f77;
        padding: .5em;
        margin: 2em;
        border-radius: 1em;
      }
      div.rbox {
        border: 1px solid #E4CB8B;
        padding: 1em;
        margin: 1em;
        border-radius: 1em;
      }
      div.rbox a {
        color: #303030;
      }
      div.service {
        background-color: #fff9eb;
      }
      div.service div.ipo {
        background-color: #fffbf2;
      }
      .red {
        background-color: #ff5050;
      }
      .green {
        background-color: #60ff60;
      }
      .blue {
        background-color: blue;
      }
      .yellow {
        background-color: yellow;
      }
      .dot {
        height: 20px;
        width: 20px;
        border-radius: 50%;
        text-align: center;
        vertical-align: middle;
        font-size: 50%;
        position: relative;
        box-shadow: inset -1px -1px 10px #000, 1px 1px 2px black, inset 0px 0px 1px black;
        display: inline-block;
        margin-right: 1em;
      }
      .dot::after {
        background-color: rgba(255, 255, 255, 0.3);
        content: '';
        height: 45%;
        width: 12%;
        position: absolute;
        top: 4%;
        left: 15%;
        border-radius: 50%;
        transform: rotate(40deg);
      }
    </style>
  </head>
  <body>
    <p id="header">onionbalance dashboard - last update: {{tstamp}} UTC</p>
    % if msg:
      <div id="msg">
        <i class="dot red"></i>
        <span>{{msg}}</span>
      </div>
    % end
    % for service in ob_services:
    <div class="service rbox">
      <p>
        % if 'not uploaded' in service.status:
        <i class="dot red"></i>
        % else:
        <i class="dot green"></i>
        % end
        <a href="http://{{service.addr}}">{{service.addr.rstrip(".onion")}}</a>
        - {{service.status}}
      </p>
      % for ipo in service.introduction_points:
        % addr = ipo[0]
        % name = addr.rstrip(".onion")
      <div class="ipo rbox">
        % if "offline" in ipo[1]:
        <i class="dot red"></i>
        <a href="https://{{addr}}">{{name}}</a>
        {{ipo[1]}}
        % else:
        <i class="dot green"></i>
        <a href="http://{{addr}}">{{name}}</a>
        - {{ipo[1]}} {{ipo[2]}} - {{ipo[3]}} Introduction Points
        % end
      </div>
      % end
    </div>
    % end
  </body>
</html>
