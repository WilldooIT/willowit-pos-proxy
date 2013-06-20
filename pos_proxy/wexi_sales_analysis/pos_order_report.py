# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import tools
from openerp.osv import fields,osv
class pos_payment_report(osv.osv):
    _name = "report.pos.payment.wexi"
    _auto = False
    _columns = {
        "order_name":fields.char(size=64,string="Order Name"),
        "order_date":fields.date(string="Order Date"),
        'year': fields.char('Year', size=4, readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'),
            ('05','May'), ('06','June'), ('07','July'), ('08','August'), ('09','September'),
            ('10','October'), ('11','November'), ('12','December')], 'Month',readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        "session_name":fields.char(size=64,string="Session Name"),
        "journal_name":fields.char(size=64,string="Payment Name"),
        "amount":fields.float(string="Amount"),
        "session_state":fields.char(size=24,string="Session State"),
    }

    def init(self,cr):
        tools.drop_view_if_exists(cr,"report_pos_payment_wexi")
        cr.execute("""
        create or replace view report_pos_payment_wexi as (
        select          max(absl.id) as id,
                        max(absl.name),
                        max(po.name) order_name,
                        max(po.date_order) order_date,
                        max(ps.name) session_name,
                        max(ps.state) session_state,
                        max(to_char(po.date_order, 'YYYY')) as year,
                        max(to_char(po.date_order, 'MM')) as month,
                        max(to_char(po.date_order, 'YYYY-MM-DD')) as day,
                        absl.journal_id,
                        sum(absl.amount) amount,
                        max(aj.name) journal_name
                    from account_bank_statement_line absl
                left join account_journal aj on (absl.journal_id = aj.id)
                        left join pos_order po on (po.id = absl.pos_statement_id)
                        left join pos_session ps on (po.session_id = ps.id)
                        where absl.type = 'customer'
                group by po.date_order, absl.journal_id)
        """)
pos_payment_report()

class pos_order_report(osv.osv):
    _name = "report.pos.order.wexi"
    _description = "Point of Sale Order Analysis"
    _auto = False
    _columns = {
        'date': fields.date('Date Order', readonly=True),
        'year': fields.char('Year', size=4, readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'),
            ('05','May'), ('06','June'), ('07','July'), ('08','August'), ('09','September'),
            ('10','October'), ('11','November'), ('12','December')], 'Month',readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'partner_id':fields.many2one('res.partner', 'Partner', readonly=True),
        'product_id':fields.many2one('product.product', 'Product', readonly=True),
        'state': fields.selection([('draft', 'New'), ('paid', 'Closed'), ('done', 'Synchronized'), ('invoiced', 'Invoiced'), ('cancel', 'Cancelled')],
                                  'Status'),
        'user_id':fields.many2one('res.users', 'Salesperson', readonly=True),
        'price_total':fields.float('Total Price', readonly=True),
        'total_discount':fields.float('Total Discount', readonly=True),
        'average_price': fields.float('Average Price', readonly=True,group_operator="avg"),
        'shop_id':fields.many2one('sale.shop', 'Shop', readonly=True),
        'company_id':fields.many2one('res.company', 'Company', readonly=True),
        'nbr':fields.integer('# of Lines', readonly=True),
        'product_qty':fields.integer('# of Qty', readonly=True),
        'journal_id': fields.many2one('account.journal', 'Journal'),
        'delay_validation': fields.integer('Delay Validation'),
        "session_id":fields.many2one("pos.session",string="Session",readonly=True),
        "session_state":fields.char(size=24,string="Session State", readonly=True),
        "line_type_code":fields.selection([
            ('NORMAL',"Normal Sale"),
            ('TSTNG',"Open bottle for Tasting"),
            ("REFUND","Refund"),
            ("W_ON","Write On"),
            ("W_OFF","Write Off")],size=24,string="Line Type", readonly=True),
    }
    _order = 'date desc'

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_pos_order_wexi')
        cr.execute("""
            create or replace view report_pos_order_wexi as (
                select
                    min(l.id) as id,
                    max(s.session_id) as session_id,
                    max(ps.state) as session_state,
                    max(l.line_type_code) as line_type_code,
                    count(*) as nbr,
                    to_date(to_char(s.date_order, 'dd-MM-YYYY'),'dd-MM-YYYY') as date,
                    sum(l.qty * u.factor) as product_qty,
                    sum((l.qty * l.price_unit) * (l.discount / 100)) as total_discount,
                    sum(price_subtotal_incl) as price_total,
                    (sum(l.qty*l.price_unit)/sum(l.qty * u.factor))::decimal(16,2) as average_price,
                    sum(cast(to_char(date_trunc('day',s.date_order) - date_trunc('day',s.create_date),'DD') as int)) as delay_validation,
                    to_char(s.date_order, 'YYYY') as year,
                    to_char(s.date_order, 'MM') as month,
                    to_char(s.date_order, 'YYYY-MM-DD') as day,
                    s.partner_id as partner_id,
                    s.state as state,
                    s.user_id as user_id,
                    s.shop_id as shop_id,
                    s.company_id as company_id,
                    s.sale_journal as journal_id,
                    l.product_id as product_id
                from pos_order_line as l
                    left join pos_order s on (s.id=l.order_id)
                    left join product_template pt on (pt.id=l.product_id)
                    left join product_uom u on (u.id=pt.uom_id)
                    left join pos_session ps on (s.session_id = ps.id)
                group by
                    to_char(s.date_order, 'dd-MM-YYYY'),to_char(s.date_order, 'YYYY'),to_char(s.date_order, 'MM'),
                    to_char(s.date_order, 'YYYY-MM-DD'), s.partner_id,s.state,
                    s.user_id,s.shop_id,s.company_id,s.sale_journal,l.product_id,s.create_date
                having
                    sum(l.qty * u.factor) != 0)""")

pos_order_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
