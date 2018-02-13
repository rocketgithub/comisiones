# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class hr_employee(osv.osv):
    _inherit = 'hr.employee'

    _columns = {
        'fecha_ingreso': fields.date('Fecha de ingreso'),
        'porcentaje_comision_primer_anio': fields.float('% Comision primer año'),
        'monto_minimo_para_comisiones': fields.float('Monto mínimo para comisiones'),
        'meta_comisiones': fields.float('Meta'),
        'porcentaje_penalizacion_meta': fields.float('% penalización por no llegar a la meta'),
        'dias_penalizacion_vencimiento': fields.integer('Dias después de vencimiento para penalización'),
        'porcentaje_penalizacion_dias_vencimiento': fields.float('% penalización dias después de vencimiento'),
        'aplica_comision_por_rangos': fields.boolean('Aplica comisión por rangos'),
        'comision_rango': fields.one2many('comisiones.rango', 'vendedor_id', string='Comisiones por rango'),
        'comision_producto': fields.one2many('comisiones.producto', 'vendedor_id', string='Comisiones por producto'),
        'comision_categoria_producto': fields.one2many('comisiones.categoria_producto', 'vendedor_id', string='Comisiones por categoria de producto'),
    }


