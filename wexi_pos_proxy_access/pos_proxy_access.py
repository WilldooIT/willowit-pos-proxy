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
        try:
            conn = httplib.HTTPConnection(pos_config.pos_proxy_url,timeout=2)
            conn.request("GET","/pos/%s?%s" % (command,urllib.urlencode(args)))
            response = conn.getresponse()
            result = response.read()
        except Exception as e:
            raise osv.except_osv("Communication error","Unable to communicate with pos_proxy: %s" % e)
        
        return result


class PosOrder(osv.osv):
    _inherit = "pos.order"

    _columns = {
        "receipt_json":fields.text(string="Receipt Json")
    }

    def action_reprint_receipt(self,cr,uid,ids,context=None):
        pos_config_obj = self.pool.get("pos.config")
        for order in self.browse(cr,uid,ids,context=context):
            config_id = order.session_id.config_id.id
            res = pos_config_obj.pos_proxy_command(cr,uid,config_id,"reprint_receipt",{"receipt":order.receipt_json or ""},context=context)
        return {"warning":{"title":"Server Sez:","message":" " + res}}
        






