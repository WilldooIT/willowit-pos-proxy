#  The code here is theoretically compatible with version 6.1, but has been developed with version 7.0 data structures
#  for testing


from osv import fields, osv

class PosSession(osv.osv):
    _inherit = "pos.session"

    def _pull_needed(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for session in self.browse(cr, uid, ids, context=context):
            result[session.id] = session.state == 'closed'
        return result

    _columns = {'pulled_centrally' : fields.selection([('sending', 'In transmission'), ('sent', 'Sent')], 'Pulled to Central Server', readonly=True),
                'pull_needed' : fields.function(_pull_needed, type='boolean', string='Pull Needed')
                }

    def write(self, cr, uid, ids, vals, context=None):
        if not('pulled_centrally') in vals:
            vals['pulled_centrally'] = False
        return super(PosSession, self).write(cr, uid, ids, vals, context=context)

    def pull_columns(self,cr,uid,id,context=None):
        account_move_line_obj = self.pool.get("account.move.line")
        account_journal_obj = self.pool.get("account.journal")

        session = self.browse(cr,uid,id,context=context)
        discrepancy_amount = 0
        for payment_method in session.config_id.journal_ids:
            if payment_method.cash_control:
                loss_moves = account_move_line_obj.search(cr,uid,
                    [('ref','=',session.name),
                    ('account_id','=',payment_method.loss_account_id.id),
                    ('name','=','Point of Sale Loss')],context=context)
                
                if loss_moves:
                    loss = account_move_line_obj.browse(cr,uid,loss_moves[0],context=context)
                    loss_amount = loss.credit + loss.debit
                else:
                    loss_amount = 0
                gain_moves = account_move_line_obj.search(cr,uid,
                    [('ref','=',session.name),
                    ('account_id','=',payment_method.profit_account_id.id)],context=context)
                
                if gain_moves:
                    gain = account_move_line_obj.browse(cr,uid,gain_moves[0],context=context)
                    gain_amount = gain.credit + gain.debit
                else:
                    gain_amount = 0

                discrepancy_amount += gain_amount - loss_amount
                
        cash_payment_method = session.config_id.journal_ids

        return {
            "name":session.name,
            "start_balance":session.cash_register_balance_start,
            "total_transaction_amount":session.cash_register_total_entry_encoding or 0,
            "end_balance":session.cash_register_balance_end_real or 0,
            "discrepancy":discrepancy_amount or 0,
            "stop_at":session.stop_at,
            "start_at":session.start_at,
            "config_name":session.config_id.name,
            "qty":len(session.order_ids),
        }
        




class PosOrder(osv.osv):

    _inherit = 'pos.order'

    def _pull_needed(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        for order in self.browse(cr, uid, ids, context=context):
            result[order.id] = order.state == 'done'
        return result

    _columns = {'pulled_centrally' : fields.selection([('sending', 'In transmission'), ('sent', 'Sent')], 'Pulled to Central Server', readonly=True),
                'pull_needed' : fields.function(_pull_needed, type='boolean', string='Pull Needed'),
                }

    def write(self, cr, uid, ids, vals, context=None):
        if not('pulled_centrally') in vals:
            vals['pulled_centrally'] = False
        return super(PosOrder, self).write(cr, uid, ids, vals, context=context)

    def pull_columns(self, cr, uid, id, context=None):
        order = self.browse(cr, uid, id, context=context)
        config_name = order.session_id.config_id.name
        salesperson_name = "%s (%d)" % (order.user_id.name,order.user_id.id)

        order_lines = [{
            "name":line.product_id.name,
            "product_id":line.product_id.id,
            "price_unit":line.price_unit,
            "price_subtotal_incl":line.price_subtotal_incl,
            "price_subtotal":line.price_subtotal,
            "discount":line.discount,
            "discount_notice":line.notice,
            "line_type_code":line.line_type_code,
            "line_note":line.line_note,
            "qty":line.qty} for line in order.lines],

        payment_types = {}
        for stmt in order.statement_ids:
            existing_line = payment_types.get(stmt.journal_id.code)
            if existing_line:
                new_line = existing_line + stmt.amount
            else:
                new_line = stmt.amount
            payment_types[stmt.journal_id.code] = new_line
        
        payment_lines = [{"name":name,"amount":amount} for (name,amount) in payment_types.iteritems()]
        order_data = {'name' : order.name,
                'date_order' : order.date_order,
                'partner_id' : order.partner_id and order.partner_id.id or False,
                'pricelist_id' : order.pricelist_id and order.pricelist_id.id or False,
                "pos_config_name":config_name,
                "session_id":order.session_id.id,
                "salesperson":salesperson_name,
                "order_lines" : order_lines,
                "payment_lines":payment_lines,
                "ref":order.pos_reference,
                "partner_id":order.partner_id and order.partner_id.id or False
                }
        return order_data

class ResPartner(osv.osv):
    _inherit = 'res.partner'

    _columns = {'pulled_centrally' : fields.selection([('sending', 'In transmission'), ('sent', 'Sent')], 'Pulled to Central Server', readonly=True)}

    def write(self, cr, uid, ids, vals, context=None):
        if not('pulled_centrally') in vals:
            vals['pulled_centrally'] = False
        return super(ResPartner, self).write(cr, uid, ids, vals, context=context)


    def pull_columns(self, cr, uid, id, context=None):
        partner = self.browse(cr, uid, id, context=context)
        #we have to do silly things like this to play nicely with central, which is v6.1 for now.
        return {'name' : partner.name, 'date' : partner.date, 'ref' : partner.date, 'vat' : partner.vat, 'website' : partner.website, 'comment' : partner.comment, 'credit_limit' : partner.credit_limit, 'ean13' : partner.ean13, 'active' : partner.active,
                'customer' : partner.customer, 'supplier' : partner.supplier, 'employee' : partner.employee,
                'winery' : partner.winery,
                'parent_id' : partner.parent_id.id, 'title' : partner.title.id,
                'address_ids' :[{
                    'type' : partner.type, 'function' : partner.function, 'name' : partner.name,
                    'street' : partner.street, 'street2' : partner.street2, 'zip' : partner.zip, 'city' : partner.city,
                    'email' : partner.email, 'phone' : partner.phone, 'fax' : partner.fax, 'mobile' : partner.mobile, 'birthdate' : partner.birthdate,
                    'active' : partner.active}]}



#class ResPartner(osv.osv):
#
#   _inherit = 'res.partner'
#
#    _columns = {'pulled_centrally' : fields.selection([('sending', 'In transmission'), ('sent', 'Sent')], 'Pulled to Central Server', readonly=True)}
#
#    def write(self, cr, uid, ids, vals, context=None):
#        if not('pulled_centrally') in vals:
#            vals['pulled_centrally'] = False
#        return super(ResPartner, self).write(cr, uid, ids, vals, context=context)
#
#    def pull_columns(self, cr, uid, id, context=None):
#        partner = self.browse(cr, uid, id, context=context)
#        return {'name' : partner.name, 'date' : partner.date, 'ref' : partner.date, 'vat' : partner.vat, 'website' : partner.website, 'comment' : partner.comment, 'credit_limit' : partner.credit_limit, 'ean13' : partner.ean13, 'active' : partner.active,
#                'customer' : partner.customer, 'supplier' : partner.supplier, 'employee' : partner.employee,
#                'winery' : partner.winery,
#                'parent_id' : partner.parent_id.id, 'title' : partner.title.id,
#                'address_ids' : [x.id for x in partner.address],
#                }


#class ResPartnerAddress(osv.osv):

#   _inherit = 'res.partner.address'

#   _columns = {'pulled_centrally' : fields.selection([('sending', 'In transmission'), ('sent', 'Sent')], 'Pulled to Central Server', readonly=True)}

#    def write(self, cr, uid, ids, vals, context=None):
#        if not('pulled_centrally') in vals:
#            vals['pulled_centrally'] = False
#        return super(ResPartnerAddress, self).write(cr, uid, ids, vals, context=context)
#
#    def pull_columns(self, cr, uid, id, context=None):
#        address = self.browse(cr, uid, id, context=context)
#        return {'type' : address.type, 'function' : address.function, 'name' : address.name,
#                'street' : address.street, 'street2' : address.street2, 'zip' : address.zip, 'city' : address.city,
#                'email' : address.email, 'phone' : address.phone, 'fax' : address.fax, 'mobile' : address.mobile, 'birthdate' : address.birthdate,
#                'active' : address.active,
#                'partner_id' : address.partner_id.id, 'title' : address.title.id, 'country_id' : address.country_id.id, 'state_id' : address.state_id.id,
#                }
