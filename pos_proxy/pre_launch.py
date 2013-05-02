import json
import os
import stat
import requests

configpath = os.environ["POS_PROXY_PATH"] + "/config.json"
config = json.load(open(configpath))
for (p_name,printer) in config["printers"].iteritems():
    try:
        if printer["type"] == "local":
            mode = os.stat(printer["device"]).st_mode | stat.S_IWOTH
            os.chmod(printer["device"],mode)
    except:
        print "Printer device not found!"
    try:
        if config.get("vfd_device"):
            mode = os.stat(config["vfd_device"]).st_mode | stat.S_IWOTH
            os.chmod(config["vfd_device"],mode)
    except:
        print "VFD not found!"

#try:
#    response = requests.get(config["cookbook_url"],verify=False)
#    if response.ok:
#        cookbook = os.environ["POS_PROXY_PATH"] + config["cookbook"]
#        if os.path.exists(cookbook):
#            os.rename(cookbook,"%s.bak" % cookbook)
#        with open(cookbook,"w") as f:
#            f.write(response.text)
#
#except Exception as e:
#    print e
