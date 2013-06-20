from osv import fields,osv
import from datetime import datetime
class LiveData(osv.osv):
    _name = "wexi.live.data"
    _auto = False
    
    def get_sales_figures(self,cr,uid,context=context):
        po_obj = self.pool.get("pos.order")
        pos_session_obj = self.pool.get("pos.session")
        
        fromdate = datetime.now().strftime("%Y-%m-%d 00:00:00")
        todays_ids = po_obj.search(cr,uid,["&",("state","=","done"),("create_date",">",fromdate)],context=context)

        for order in po_obj.browse(cr,uid,todays_ids,context=context):
            pass
        
        res = {}
        

