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

class comisiones_calculo_wizard2(osv.osv_memory):
    _name = 'comisiones.calculo.wizard2'

    _columns = {
        'vendedor_id': fields.many2one('hr.employee', 'Empleado', required=True),
        'fecha_inicio': fields.date('Fecha inicio', required=True),
        'fecha_fin': fields.date('Fecha fin', required=True),
        'archivo': fields.binary('Archivo'),
    }

    def _default_vendedor(self, cr, uid, context):
        if 'active_id' in context:
            return context['active_id']
        return False

    _defaults = {
        'vendedor_id': _default_vendedor,
    }

    def obtener_categoria_padre(self, cr, uid, categoria, categorias_en_rango):
        categoria_producto_padre = categoria
        lista_categorias_padres = [categoria]
        while (categoria_producto_padre != False):
            categoria_hija = self.pool.get('product.category').browse(cr, uid, categoria_producto_padre)
            if categoria_hija.id in categorias_en_rango:
                lista_categorias_padres.append(categoria_hija.id)

            categoria_producto_padre = categoria_hija.parent_id.id

        categoria = lista_categorias_padres.pop()
        return categoria

    #Concateno numeros de pago y fechas de pago, en caso que sean varios pagos para esta factura, y poder desplegarlos
    #en una misma celda del csv.
    def obtener_numero_y_fecha_pagos(self, cr, uid, invoice):
        res = {}
        res['numero_pago'] = ''
        res['fecha_pago'] = ''
        z = 0
        for payment_id in invoice.payment_ids:
            if z > 0:
                res['numero_pago'] += ', '
                res['fecha_pago'] += ', '
            res['numero_pago'] = res['numero_pago'] + payment_id.ref
            res['fecha_pago'] = res['fecha_pago'] + payment_id.date
            z += 1

        return res


    #Reviso si la fecha del último pago se realizó fuera de tiempo, y calculo la penalización respectiva.
    def calcular_monto_penalizacion_vencimiento(self, cr, uid, vendedor, invoice, monto_comision_factura):
        monto_penalizacion_vencimiento = 0
        if invoice.date_due:
            fecha_mayor_pago = None
            for payment_id in invoice.payment_ids:
                if fecha_mayor_pago is None:
                    fecha_mayor_pago = payment_id.date
                elif fecha_mayor_pago < payment_id.date:
                    fecha_mayor_pago = payment_id.date
            r = relativedelta.relativedelta(parser.parse(fecha_mayor_pago), parser.parse(invoice.date_due))
            diferencia_dias = (r.years * 365) + (r.months * 30) + r.days
            if diferencia_dias > vendedor.dias_penalizacion_vencimiento:
                monto_penalizacion_vencimiento = monto_comision_factura * (vendedor.porcentaje_penalizacion_dias_vencimiento / 100)

        return monto_penalizacion_vencimiento


    #Las comisiones pueden generarse por rango de ventas. Pero pueden haber comisiones por rango de ventas de categoría.
    #Entonces puede existir no solo un porcentaje de comisiones, sino que puede existir un porcentaje de comisiones para
    #cada rango de ventas por categoría, y un porcentaje de comisión para rangos de ventas sin categoría o que la categoría
    #no está definida en los rangos.
    def comisiones_por_rango(self, cr, uid, vendedor, hoja, invoice_ids):
        #Genero un array con los ids de las categorías de producto que si están definidas en los rangos, e inicializo diccionarios.
        categorias_en_rango = []
        subtotales_categoria = {}
        comision_por_categoria = {}
        for rango in vendedor.comision_rango:
            #Si este rango tiene definida categoría, y aún no está en el array categorias_en_rango, agrego el id.
            if rango.categ_id and rango.categ_id.id not in categorias_en_rango:
                categorias_en_rango.append(rango.categ_id.id)
                subtotales_categoria[rango.categ_id.id] = 0
                comision_por_categoria[rango.categ_id.id] = 0

        #Como los rangos pueden ser por categoría, calculo subtotales globales para cada categoria de productos definida en categorias_en_rango.
        #Los subtotales de cada categoría quedan guardados en el diccionario subtotales_categorias.
        #La suma de las ventas que no tienen categorías relacionadas, o de categorías que no aparecen en los rangos, se guardan en la variable
        #subtotal_sin_categoria
        subtotal_sin_categoria = 0
        for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids):
            for invoice_line in invoice.invoice_line:
                #Reviso si el producto tiene categoría, y si esta está definida en los rangos de comisiones (categorias_en_rango).
                #Si es verdadero, voy calculando la sumatoria por categorías. De lo contrario, suma en la variable subtotal_sin_categoria.
                categoria = self.obtener_categoria_padre(cr,uid,invoice_line.product_id.categ_id.id,categorias_en_rango)
                if invoice_line.product_id.categ_id and categoria in categorias_en_rango:
                    subtotales_categoria[categoria] += invoice_line.price_subtotal
                else:
                    subtotal_sin_categoria += invoice_line.price_subtotal

        #Ya teniendo los subtotales por categoría y subtotal_sin_categoria, se puede revisar en qué rango de comisión aplica ese subtotal
        #para una categoría determinada, y en qué rango está el subtotal sin categoría, y así poder averiguar el porcentaje de comisión por
        #categoría, lo cual queda guardado en comision_por_categoria[categ_id], y averiguar el porcentaje de comisión para las ventas sin
        #categoría, lo cual queda guardado en porcentaje_comision_sin_categoria.
        porcentaje_comision_sin_categoria = 0
        for rango in vendedor.comision_rango:
            if rango.categ_id:
                if rango.minimo <= subtotales_categoria[rango.categ_id.id] and rango.maximo >= subtotales_categoria[rango.categ_id.id]:
                    comision_por_categoria[rango.categ_id.id] = rango.porcentaje_comision
            else:
                if rango.minimo <= subtotal_sin_categoria and rango.maximo >= subtotal_sin_categoria:
                    porcentaje_comision_sin_categoria = rango.porcentaje_comision

        monto_subtotal_vendido = 0
        for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids):
            monto_subtotal_vendido += invoice.amount_untaxed

        logging.getLogger('MONTO VENDIDO... ').warn(monto_subtotal_vendido)
        if monto_subtotal_vendido < vendedor.monto_minimo_para_comisiones:
            hoja.write(3, 0, 'El monto vendido no es suficiente para obtener comisiones: ' + str(monto_subtotal_vendido))
        else:
            #Reviso si va a aplicar penalización por no haber llegado a la meta de ventas.
            porcentaje_penalizacion_meta = 0
            if monto_subtotal_vendido < vendedor.meta_comisiones:
                porcentaje_penalizacion_meta = vendedor.porcentaje_penalizacion_meta

            #Ya teniendo los porcentajes de comisión para cada rango de categorías, recorro las facturas y valido.
            y = 10
            for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids):
                monto_comision_factura = 0

                hoja.write(y, 0, invoice.origin)
                hoja.write(y, 1, invoice.number)
                hoja.write(y, 2, invoice.date_invoice)
                hoja.write(y, 3, invoice.date_due)
                hoja.write(y, 4, invoice.amount_total)

                datos_pago = self.obtener_numero_y_fecha_pagos(cr, uid, invoice)
                hoja.write(y, 5, datos_pago['numero_pago'])
                hoja.write(y, 6, datos_pago['fecha_pago'])

                for invoice_line in invoice.invoice_line:
                    categoria = self.obtener_categoria_padre(cr,uid,invoice_line.product_id.categ_id.id,categorias_en_rango)
                    if invoice_line.product_id.categ_id and categoria in categorias_en_rango:
                        monto_comision_linea = invoice_line.price_subtotal * (comision_por_categoria[categoria] / 100)
                    else:
                        monto_comision_linea = invoice_line.price_subtotal * (porcentaje_comision_sin_categoria / 100)

                    monto_comision_factura += monto_comision_linea

                hoja.write(y, 7, monto_comision_factura)

                monto_penalizacion_vencimiento = self.calcular_monto_penalizacion_vencimiento(cr, uid, vendedor, invoice, monto_comision_factura)
                monto_comision_factura = monto_comision_factura - monto_penalizacion_vencimiento

                monto_penalizacion_meta = 0
                if porcentaje_penalizacion_meta > 0:
                    monto_penalizacion_meta = monto_comision_factura * (porcentaje_penalizacion_meta / 100)
                monto_comision_factura = monto_comision_factura - monto_penalizacion_meta - monto_penalizacion_vencimiento




                hoja.write(y, 8, monto_penalizacion_meta) #Para comisiones por rango, no aplica penalización por no llegar a la meta.
                hoja.write(y, 9, monto_penalizacion_vencimiento)
                hoja.write(y, 10, monto_comision_factura)

                y += 1

    #Si las comisiones no se calculan por rango de ventas, se pueden calcular por comisiones por producto o comisiones por categoría de producto.
    #Si el vendedor tiene menos de un año como vendedor, le puede aplicar una comisión fija por ser nuevo, y entonces no aplicarle ninguno de los
    #modelos de comisiones anteriores. Cómo el código para calcular comisiones por producto o categoría de producto, y el código para calcular
    #comisiones si es un vendedor con menos de un año es prácticamente el mismo, entonces para no duplicar código, se está calculando ambos modelos
    #en esta misma función.
    def comisiones_por_producto_o_vendedor_nuevo(self, cr, uid, vendedor, hoja, invoice_ids, fecha_inicio):

        #Reviso si el vendedor tiene menos de un año. Al vendedor le aplica una comisión fija durante el primer año. Si el vendedor tiene configurado
        #el valor 0 en el porcentaje de comision del primer año, o no tiene configurado fecha de ingreso, entonces no le aplica el modelo de comisión
        #para nuevos.
        porcentaje_comision_nuevo = 0
        if vendedor.fecha_ingreso and vendedor.porcentaje_comision_primer_anio > 0:
            r = relativedelta.relativedelta(parser.parse(fecha_inicio), parser.parse(vendedor.fecha_ingreso))
            if r.years == 0:
                porcentaje_comision_nuevo = vendedor.porcentaje_comision_primer_anio

        #Calculo el subtotal global vendido, para compararlo con el mínimo de ventas requerido para obtener comisiones,
        #y para compararlo con el monto meta.
        monto_subtotal_vendido = 0
        for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids):
            monto_subtotal_vendido += invoice.amount_untaxed

        logging.getLogger('MONTO VENDIDO... ').warn(monto_subtotal_vendido)
        if monto_subtotal_vendido < vendedor.monto_minimo_para_comisiones:
            hoja.write(3, 0, 'El monto vendido no es suficiente para obtener comisiones')
        else:

            #Reviso si va a aplicar penalización por no haber llegado a la meta de ventas.
            porcentaje_penalizacion_meta = 0
            if monto_subtotal_vendido < vendedor.meta_comisiones:
                porcentaje_penalizacion_meta = vendedor.porcentaje_penalizacion_meta

            #Recorro las facturas para agregar al csv datos de la factura, y calculo la comisión de cada factura para agregarla al csv.
            y = 3
            for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids):
                monto_comision_factura = 0
                hoja.write(y, 0, invoice.origin)
                hoja.write(y, 1, invoice.number)
                hoja.write(y, 2, invoice.date_invoice)
                hoja.write(y, 3, invoice.date_due)
                hoja.write(y, 4, invoice.amount_total)

                datos_pago = self.obtener_numero_y_fecha_pagos(cr, uid, invoice)
                hoja.write(y, 5, datos_pago['numero_pago'])
                hoja.write(y, 6, datos_pago['fecha_pago'])

                #Calculo la comisión por línea de factura, ya que la comisión puede ser por producto o por categoría de producto
                #(o comisión de nuevo vendedor)
                for invoice_line in invoice.invoice_line:
                    porcentaje_comision_linea = 0
                    if porcentaje_comision_nuevo > 0:
                        porcentaje_comision_linea = porcentaje_comision_nuevo
                    else:
                        #Reviso si el vendedor tiene configurada comisión para este producto
                        for comision_producto in vendedor.comision_producto:
                            if comision_producto.product_id.id == invoice_line.product_id.id:
                                porcentaje_comision_linea = comision_producto.porcentaje_comision

                        #Si no se encontró comisión para el producto, reviso si el vendedor tiene cofigurada comisión para la categoría del producto
                        if porcentaje_comision_linea == 0:
                            for comision_categoria_producto in vendedor.comision_categoria_producto:
                                if comision_categoria_producto.categ_id.id == invoice_line.product_id.categ_id.id:
                                    porcentaje_comision_linea = comision_categoria_producto.porcentaje_comision

                    monto_comision_linea = invoice_line.price_subtotal * (porcentaje_comision_linea / 100)
                    monto_comision_factura += monto_comision_linea

                hoja.write(y, 7, monto_comision_factura)

                monto_penalizacion_meta = 0
                if porcentaje_penalizacion_meta > 0:
                    monto_penalizacion_meta = monto_comision_factura * (porcentaje_penalizacion_meta / 100)

                monto_penalizacion_vencimiento = self.calcular_monto_penalizacion_vencimiento(cr, uid, vendedor, invoice, monto_comision_factura)
                monto_comision_factura = monto_comision_factura - monto_penalizacion_meta - monto_penalizacion_vencimiento

                hoja.write(y, 8, monto_penalizacion_meta)
                hoja.write(y, 9, monto_penalizacion_vencimiento)
                hoja.write(y, 10, monto_comision_factura)
                y += 1


    def generar(self, cr, uid, ids, context=None):
        for w in self.browse(cr, uid, ids):
            libro = xlwt.Workbook()
            hoja = libro.add_sheet('reporte')

            xlwt.add_palette_colour("custom_colour", 0x21)
            libro.set_colour_RGB(0x21, 200, 200, 200)
            estilo = xlwt.easyxf('pattern: pattern solid, fore_colour custom_colour')

            hoja.write(0, 0, 'VENDEDOR')
            hoja.write(0, 1, w.vendedor_id.name)
            hoja.write(2, 0, 'Numero SO')
            hoja.write(2, 1, 'Numero de factura')
            hoja.write(2, 2, 'Fecha de la factura')
            hoja.write(2, 3, 'Fecha de vencimiento')
            hoja.write(2, 4, 'Monto de la factura')
            hoja.write(2, 5, 'Numero de pago')
            hoja.write(2, 6, 'Fecha de pago')
            hoja.write(2, 7, 'Monto comision sin penalizacion')
            hoja.write(2, 8, 'Penalizacion por meta')
            hoja.write(2, 9, 'Penalizacion por vencimiento')
            hoja.write(2, 10, 'Monto comision real')

            #Obtengo los ids de las facturas en las cuales se van a calcular las comisiones: invoice_ids
            move_ids = []
#            voucher_line_ids = self.pool.get('account.voucher.line').search(cr, uid, [('date_original', '>=', w.fecha_inicio), ('date_original', '<=', w.fecha_fin)])
            voucher_line_ids = self.pool.get('account.voucher.line').search(cr, uid, [('voucher_id.date', '>=', w.fecha_inicio), ('voucher_id.date', '<=', w.fecha_fin)])
            for voucher_line in self.pool.get('account.voucher.line').browse(cr, uid, voucher_line_ids, context=context):
                move_ids.append(voucher_line.move_line_id.move_id.id)

            temp_invoice_ids = self.pool.get('account.invoice').search(cr, uid, [('user_id', '=', w.vendedor_id.user_id.id), ('type', '=', 'out_invoice'), ('move_id', 'in', move_ids), ('state', '=', 'paid'), ('no_calcular_comision', '=', False)],order='date_invoice asc')
            logging.warn('Facturas temporales')
            logging.warn(temp_invoice_ids)
            invoice_ids = []
            for invoice in self.pool.get('account.invoice').browse(cr, uid, temp_invoice_ids, context=context):
                fecha_mayor = False
                for payment_id in invoice.payment_ids:
                    if payment_id.date > w.fecha_fin:
                        fecha_mayor = True
                if fecha_mayor == False:
                    invoice_ids.append(invoice.id)

            logging.warn('FACTURAS IDS... ')
            logging.warn(invoice_ids)
            vendedor = self.pool.get('hr.employee').browse(cr, uid, w.vendedor_id.id, context=context)

            if vendedor.aplica_comision_por_rangos:
                self.comisiones_por_rango(cr, uid, vendedor, hoja, invoice_ids)
            else:
                self.comisiones_por_producto_o_vendedor_nuevo(cr, uid, vendedor, hoja, invoice_ids, w.fecha_inicio)

            f = StringIO.StringIO()
            libro.save(f)
            datos = base64.b64encode(f.getvalue())
            self.write(cr, uid, ids, {'archivo':datos})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'comisiones.calculo.wizard2',
            'res_id': ids[0],
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
