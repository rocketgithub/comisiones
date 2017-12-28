# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class res_users(osv.osv):
    _inherit = 'res.users'

    _columns = {
        'fecha_ingreso': fields.date('Fecha de ingreso'),

        'porcentaje_comision_primer_anio': fields.float('% Comision primer año'),
        'monto_minimo_para_comisiones': fields.float('Monto mínimo para comisiones'),
        'meta_comisiones': fields.float('Meta'),
        'porcentaje_penalizacion_meta': fields.float('% penalización por no llegar a la meta'),
        'dias_penalizacion_vencimiento': fields.integer('Dias después de Vencimiento para penalización'),
        'porcentaje_penalizacion_dias_vencimiento': fields.float('% penalización dias después de Vencimiento'),
        'aplica_comision_por_rangos': fields.boolean('Aplica comisión por rangos'),
        'comision_rango': fields.one2many('comisiones.rango', 'user_id', string='Comisiones por rango'),
        'comision_producto': fields.one2many('comisiones.producto', 'user_id', string='Comisiones por producto'),
        'comision_categoria_producto': fields.one2many('comisiones.categoria_producto', 'user_id', string='Comisiones por categoria de producto'),
    }


