# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class account_invoice(osv.osv):
    _inherit = "account.invoice"

    _columns = {
        'no_calcular_comision': fields.boolean('No calcular comisión'),
    }

