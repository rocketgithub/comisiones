# -*- encoding: utf-8 -*-

from openerp.osv import osv, fields
import base64
import xlwt
import StringIO
import logging
from openerp.addons.l10n_gt_extra.a_letras import num_a_letras
from dateutil import relativedelta
from dateutil import parser
import datetime

class comisiones_calculo_wizard(osv.osv_memory):
    _name = 'comisiones.calculo.wizard'

    _columns = {
        'usuario_id': fields.many2one('res.users', 'Usuario', required=True),
        'fecha_inicio': fields.date('Fecha inicio', required=True),
        'fecha_fin': fields.date('Fecha fin', required=True),
        'archivo': fields.binary('Archivo'),
    }

    def _default_usuario(self, cr, uid, context):
        if 'active_id' in context:
            return context['active_id']
        return False

    _defaults = {
        'usuario_id': _default_usuario,
    }

    def generar(self, cr, uid, ids, context=None):
        for w in self.browse(cr, uid, ids):
            libro = xlwt.Workbook()
            hoja = libro.add_sheet('reporte')

            xlwt.add_palette_colour("custom_colour", 0x21)
            libro.set_colour_RGB(0x21, 200, 200, 200)
            estilo = xlwt.easyxf('pattern: pattern solid, fore_colour custom_colour')

            hoja.write(0, 0, 'VENDEDOR')
            hoja.write(0, 1, w.usuario_id.name)
            hoja.write(2, 0, 'Numero SO')
            hoja.write(2, 1, 'Numero de factura')
            hoja.write(2, 2, 'Fecha de la factura')
            hoja.write(2, 3, 'Monto de la factura')
            hoja.write(2, 4, 'Numero de pago')
            hoja.write(2, 5, 'Fecha de pago')
            hoja.write(2, 6, 'Monto comision')

            usuario = self.pool.get('res.users').browse(cr, uid, w.usuario_id.id, context=context)
            
            #Reviso si el usuario tiene menos de un año. Al usuario le aplica una comisión fija durante el primer año.
            r = relativedelta.relativedelta(datetime.date.today(), parser.parse(usuario.fecha_ingreso))
            porcentaje_comision_nuevo = None
            if r.years == 0:
                porcentaje_comision_nuevo = usuario.porcentaje_comision_primer_anio

            move_ids = []
            voucher_line_ids = self.pool.get('account.voucher.line').search(cr, uid, [('date_original', '>=', w.fecha_inicio), ('date_original', '<=', w.fecha_fin)])
            logging.warn(voucher_line_ids)
            for voucher_line_id in voucher_line_ids:
                voucher_line = self.pool.get('account.voucher.line').browse(cr, uid, voucher_line_id, context=context)
                move_ids.append(voucher_line.move_line_id.move_id.id)

            invoice_ids = self.pool.get('account.invoice').search(cr, uid, [('move_id', 'in', move_ids), ('state', '=', 'paid'), ('no_calcular_comision', '=', False)])

            #Si para este usuario aplica comisiones por rango, hago el calculo de comisiones basado en a tabla de rangos. De lo contrario calculo comisiones por producto o categoría de producto.
            if usuario.aplica_comision_por_rangos and porcentaje_comision_nuevo is not None:
                categorias_en_rango = []
                for rango in usuario.comision_rango:
                    if rango.categ_id and rango.categ_id not in categorias_en_rango:
                        categorias_en_rango.append(rango.categ_id)
                    
                
                #Los rangos pueden ser por categoría, por lo tanto Calculo subtotales globales por categoria de productos
                subtotales_categoria = {}
#                comision_por_categoria = {}
                subtotal_global = 0
                for invoice_id in invoice_ids:
                    invoice = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
                    for invoice_line in invoice.invoice_line:
                        if invoice_line.product_id.categ_id and invoice_line.product_id.categ_id in categorias_en_rango:                        
                            if invoice_line.product_id.categ_id in subtotales_categoria:
                                subtotales_categoria[invoice_line.product_id.categ_id] += invoice_line.product_id.price_subtotal
                            else:
                                subtotales_categoria[invoice_line.product_id.categ_id] = invoice_line.product_id.price_subtotal
#                                comision_por_categoria[invoice_line.product_id.categ_id] = 0

                        else:
                            subtotal_global += invoice_line.product_id.price_subtotal
                        
                comision_por_categoria = {}
                for categ_id in subtotales_categoria:
                    for rango in usuario.comision_rango:
                        if (rango.categ_id == categ_id) and (rango.minimo <= subtotales_categoria[categ_id] and rango.maximo >= subtotales_categoria[categ_id]):
                            comision_por_categoria[categ_id] = rango.porcentaje_comision

                porcentaje_comision_global = 0
                for rango in usuario.comision_rango:
                    if not rango.categ_id and rango.minimo <= subtotal_global and rango.maximo >= subtotal_global:
                        porcentaje_comision_global = rango.porcentaje_comision

                monto_comision_factura = 0
                for invoice_id in invoice_ids:
                    hoja.write(y, 0, invoice.origin)
                    hoja.write(y, 1, invoice.number)
                    hoja.write(y, 2, invoice.date_invoice)
                    hoja.write(y, 3, invoice.amount_total)

                    #Concateno numeros de pago y fechas de pago, en caso que sean varios pagos para esta factura, y poder desplegarlos en una misma celda del csv.
                    numero_pago = ''
                    fecha_pago = ''
                    z = 0
                    for payment_id in invoice.payment_ids:
                        z += 1
                        if z > 1:
                            numero_pago += ', '
                            fecha_pago += ', '
                        numero_pago = numero_pago + str(payment_id.ref)
                        fecha_pago = fecha_pago + str(payment_id.date)
                    hoja.write(y, 4, numero_pago)
                    hoja.write(y, 5, fecha_pago)

                    invoice = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
                    monto_comision_linea = 0
                    for invoice_line in invoice.invoice_line:
                        if invoice_line.product_id.categ_id and invoice_line.product_id.categ_id in categorias_en_rango: 
                            monto_comision_linea = invoice_line.price_subtotal * (comision_por_categoria[invoice_line.product_id.categ_id] / 100)
                        else:
                            monto_comision_linea = invoice_line.price_subtotal * (porcentaje_comision_global / 100)
                        
                        monto_comision_factura += monto_comision_linea

                    hoja.write(y, 6, monto_comision_factura)
                    y += 1

            else:
                #Calculo el subtotal global vendido, para compararlo con el mínimo de ventas requerido para obtener comisiones, y para compararlo con el monto meta.
                monto_subtotal_vendido = 0
                for invoice_id in invoice_ids:
                    invoice = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
                    monto_subtotal_vendido += invoice.amount_untaxed

                if monto_subtotal_vendido < usuario.monto_minimo_para_comisiones:
                    hoja.write(3, 0, 'El monto vendido no es suficiente para obtener comisiones')
                else:

                    porcentaje_penalizacion_meta = None
                    if monto_subtotal_vendido < usuario.meta_comisiones:
                        porcentaje_penalizacion_meta = usuario.porcentaje_penalizacion_meta
                
                    #Recorro las facturas para agregar al csv datos de la factura, y calculo la comisión de cada factura para agregarla al csv.
                    y = 3
                    monto_comision_factura = 0
                    for invoice_id in invoice_ids:

                        invoice = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
                        hoja.write(y, 0, invoice.origin)
                        hoja.write(y, 1, invoice.number)
                        hoja.write(y, 2, invoice.date_invoice)
                        hoja.write(y, 3, invoice.amount_total)

                        #Concateno numeros de pago y fechas de pago, en caso que sean varios pagos para esta factura, y poder desplegarlos en una misma celda del csv.
                        numero_pago = ''
                        fecha_pago = ''
                        z = 0
                        for payment_id in invoice.payment_ids:
                            z += 1
                            if z > 1:
                                numero_pago += ', '
                                fecha_pago += ', '
                            numero_pago = numero_pago + str(payment_id.ref)
                            fecha_pago = fecha_pago + str(payment_id.date)
                        hoja.write(y, 4, numero_pago)
                        hoja.write(y, 5, fecha_pago)

                        #Calculo la comisión por línea de factura, ya que la comisión puede ser por producto o por categoría de producto (o comisión de nuevo vendedor)
                        monto_comision_linea = 0
                        for invoice_line in invoice.invoice_line:
                            porcentaje_comision_linea = 0
                            if porcentaje_comision_nuevo != None:
                                porcentaje_comision_linea = porcentaje_comision_nuevo
                            else:
                                #Reviso si el usuario tiene cofigurada comisión para este producto
                                for comision_producto in usuario.comision_producto:
                                    if comision_producto.product_id == invoice_line.product_id:
                                        porcentaje_comision_linea = comision_producto.porcentaje_comision

                                #Si no se encontró comisión para el producto, reviso si el usuario tiene cofigurada comisión para la categoría del producto
                                if porcentaje_comision_linea == 0:
                                    for comision_categoria_producto in usuario.comision_categoria_producto:
                                        if comision_categoria_producto.categ_id == invoice_line.product_id.categ_id:
                                            porcentaje_comision_linea = comision_categoria_producto.porcentaje_comision

                            monto_comision_linea = invoice_line.price_subtotal * (porcentaje_comision_linea / 100)
                            monto_penalizacion_meta = 0
                            if porcentaje_penalizacion_meta is not None:
                                monto_penalizacion_meta = monto_comision_linea -  (monto_comision_linea * (porcentaje_penalizacion_meta / 100))
                            
                            fecha_mayor_pago = None
                            for payment_id in invoice.payment_ids:
                                if fecha_mayor_pago is None:
                                    fecha_mayor_pago = payment_id.date
                                elif fecha_mayor_pago < payment_id.date:
                                    fecha_mayor_pago = payment_id.date
                            r = relativedelta.relativedelta(parser.parse(fecha_mayor_pago), parser.parse(invoice.date_due))
                            monto_penalizacion_vencimiento = 0
                            if r.days > usuario.dias_penalizacion_vencimiento:
                                monto_penalizacion_vencimiento = monto_comision_linea - (monto_comision_linea * (porcentaje_penalizacion_dias_vencimiento / 100))

                            monto_comision_linea = monto_comision_linea - monto_penalizacion_meta - monto_penalizacion_vencimiento
                            monto_comision_factura += monto_comision_linea

                        hoja.write(y, 6, monto_comision_factura)
                        y += 1

            f = StringIO.StringIO()
            libro.save(f)
            datos = base64.b64encode(f.getvalue())
            self.write(cr, uid, ids, {'archivo':datos})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'comisiones.calculo.wizard',
            'res_id': ids[0],
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
