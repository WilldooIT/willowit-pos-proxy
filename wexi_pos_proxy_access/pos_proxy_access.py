from osv import osv, fields
import httplib,urllib

class PosConfig(osv.osv):
    _inherit = "pos.config"

    _columns = {
        "pos_proxy_url":fields.char(size=256,string="pos_proxy Url")
    }

    def pos_proxy_command(self,cr,uid,id,command,args,context=None):
        """
            Send a command to the specified POS proxy
        """
        pos_config = self.browse(cr,uid,id,context=context)
        if not pos_config.pos_proxy_url:
            raise osv.except_osv("Error","There is no proxy configured for this POS")
        try:
            conn = httplib.HTTPConnection(pos_config.pos_proxy_url,timeout=2)
            conn.request("GET","/pos/%s?%s" % (command,urllib.urlencode(args)))
            response = conn.getresponse()
            result = response.read()
        except Exception as e:
            raise osv.except_osv("Communication error","Unable to communicate with pos_proxy: %s" % e)
        
        return result








