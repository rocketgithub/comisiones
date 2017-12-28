# -*- coding: utf-8 -*-

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp

class comisiones_por_producto(osv.osv):
    _name = 'comisiones.producto'

    _columns = {
        'user_id': fields.many2one('res.users', 'Vendedor'),
        'product_id': fields.many2one('product.product', string='Producto'),
        'porcentaje_comision': fields.float('% Comision'),
    }

class comisiones_por_categoria_producto(osv.osv):
    _name = 'comisiones.categoria_producto'

    _columns = {
        'user_id': fields.many2one('res.users', 'Vendedor'),
        'categ_id': fields.many2one('product.category', string='Categoria de producto'),
        'porcentaje_comision': fields.float('% Comision'),
    }


class comisiones_por_rango(osv.osv):
    _name = 'comisiones.rango'

    _columns = {
        'user_id': fields.many2one('res.users', 'Vendedor'),
        'categ_id': fields.many2one('product.category', string='Categoria de producto'),
        'minimo': fields.float('Minimo', required=True),
        'maximo': fields.float('Maximo', required=True),
        'porcentaje_comision': fields.float('% Comision', required=True),
    }
    _order = 'categ_id, minimo asc'
