from osv import fields, osv


class PosOrder(osv.osv):
    _inherit = "pos.order"

    _columns = {
        "receipt_json":fields.text(string="Receipt Json")
    }
    def create_from_ui(self,cr,uid,orders,context=None):
        res = super(PosOrder,self).create_from_ui(cr,uid,orders,context=context)
        for order_br in self.browse(cr,uid,res,context=context):
            for order_data in orders:
                if order_data["data"]["name"] == order_br.pos_reference and order_data["data"].get("receipt_json"):
                    self.write(cr,uid,order_br.id,{"receipt_json":order_data["data"]["receipt_json"]})

        return res
    def action_reprint_receipt(self,cr,uid,ids,context=None):
        pos_config_obj = self.pool.get("pos.config")
        for order in self.browse(cr,uid,ids,context=context):
            if not order.receipt_json:
                raise osv.except_osv("Error","Sorry, there is no reprint information stored against this transaction.")
            config_id = order.session_id.config_id.id
            res = pos_config_obj.pos_proxy_command(cr,uid,config_id,"reprint_receipt",{"receipt":order.receipt_json or ""},context=context)
        return {}
        
