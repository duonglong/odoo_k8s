# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from io import BytesIO
try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class SofaExportWizard(models.TransientModel):
    _name = 'sofa.export.wizard'
    _description = 'Sofa Quote Export Wizard'

    quote_id = fields.Many2one('sofa.price.quote', 'Quote', required=True)
    template_type = fields.Selection([
        ('template1', 'Template 1: Cost by Detail Components'),
        ('template2', 'Template 2: Cost by Component Display'),
        ('template3', 'Template 3: Selling Price Export'),
    ], string='Template Type', required=True, default='template1')
    
    file_data = fields.Binary('File', readonly=True)
    file_name = fields.Char('Filename', readonly=True)
    state = fields.Selection([
        ('choose', 'Choose'),
        ('get', 'Get'),
    ], default='choose')

    @api.model
    def default_get(self, fields_list):
        """Get quote from context"""
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            res['quote_id'] = self.env.context['active_id']
        return res

    def action_export(self):
        """Export quote to Excel"""
        self.ensure_one()
        
        if not xlsxwriter:
            raise UserError(_('Please install xlsxwriter: pip install xlsxwriter'))
        
        # Generate Excel file
        if self.template_type == 'template1':
            file_data, filename = self._generate_template1()
        elif self.template_type == 'template2':
            file_data, filename = self._generate_template2()
        else:  # template3
            file_data, filename = self._generate_template3()
        
        self.write({
            'file_data': file_data,
            'file_name': filename,
            'state': 'get',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sofa.export.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _generate_template1(self):
        """Generate Template 1: Cost by Detail Components"""
        quote = self.quote_id
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Cost Detail')
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })
        data_format = workbook.add_format({'border': 1})
        money_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        
        # Headers
        headers = [
            'Product Series', 'Combination ID', 'Sofa Component', 'Sofa Component Description',
            'Config', 'Front Article', 'Back Article', 'Sofa leg', 'STD/FR', 'Foam Category',
            'Voltage', 'Material', 'Material Description', 'Material Group', 'Price/Unit',
            'Unit', 'Price Unit Qty', 'Unit Price', 'Quantity', 'Duty (Unit Price + Duty)',
            'Freight/Unit', 'Duty (Unit Freight + Duty)', 'Total BOM Cost/Unit', 'Total BOM Cost'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data
        row = 1
        for component in quote.component_ids:
            for material in component.material_ids:
                worksheet.write(row, 0, quote.series_id.full_name or quote.series_id.name, data_format)
                worksheet.write(row, 1, quote.name, data_format)
                worksheet.write(row, 2, component.component_code, data_format)
                worksheet.write(row, 3, component.component_name, data_format)
                worksheet.write(row, 4, quote.configuration_code or '', data_format)
                worksheet.write(row, 5, component.article_front_id.code or '', data_format)
                worksheet.write(row, 6, component.article_back_id.code or 'No', data_format)
                # Get options by type
                leg_opt = component.option_ids.filtered(lambda o: o.option_type_id.code == 'LEG')[:1]
                foam_opt = component.option_ids.filtered(lambda o: o.option_type_id.code == 'FOAM')[:1]
                volt_opt = component.option_ids.filtered(lambda o: o.option_type_id.code == 'VOLT')[:1]
                
                worksheet.write(row, 7, leg_opt.code if leg_opt else '', data_format)
                worksheet.write(row, 8, component.std_fr.upper() if component.std_fr else '', data_format)
                worksheet.write(row, 9, foam_opt.code if foam_opt else '', data_format)
                worksheet.write(row, 10, volt_opt.code if volt_opt else '', data_format)
                worksheet.write(row, 11, material.product_id.default_code or '', data_format)
                worksheet.write(row, 12, material.product_id.name or '', data_format)
                worksheet.write(row, 13, material.product_id.categ_id.name or '', data_format)
                worksheet.write(row, 14, material.unit_price, money_format)
                worksheet.write(row, 15, material.uom_id.name, data_format)
                worksheet.write(row, 16, material.price_unit_qty, data_format)
                
                # Calculate unit price
                unit_price = material.unit_price / material.price_unit_qty if material.price_unit_qty else material.unit_price
                worksheet.write(row, 17, unit_price, money_format)
                worksheet.write(row, 18, material.quantity, data_format)
                worksheet.write(row, 19, material.unit_price_with_duty, money_format)
                
                # Freight per unit
                freight_per_unit = material.freight_cost / material.quantity if material.quantity else 0
                worksheet.write(row, 20, freight_per_unit, money_format)
                worksheet.write(row, 21, material.freight_per_unit_with_duty, money_format)
                
                # Total BOM cost per unit
                cost_per_unit = material.material_cost / material.quantity if material.quantity else 0
                worksheet.write(row, 22, cost_per_unit, money_format)
                worksheet.write(row, 23, material.material_cost + material.freight_cost, money_format)
                
                row += 1
        
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        filename = f'Quote_{quote.name}_Cost_Detail.xlsx'
        
        return file_data, filename

    def _generate_template2(self):
        """Generate Template 2: Cost by Component Display"""
        quote = self.quote_id
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Component Summary')
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'center',
        })
        data_format = workbook.add_format({'border': 1})
        money_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        
        # Headers
        headers = [
            'Product Series', 'Combination ID', 'Sofa Component', 'Sofa Component Description',
            'Config', 'Front Article', 'Back Article', 'Front Usage', 'Front Cost',
            'Back Usage', 'Back Cost', 'Total Accessory', 'Foam Category', 'Sofa leg',
            'STD/Fire resistant', 'Voltage', 'BOM cost by sofa components', 'Simulation Created On'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data
        row = 1
        for component in quote.component_ids:
            worksheet.write(row, 0, quote.series_id.full_name or quote.series_id.name, data_format)
            worksheet.write(row, 1, quote.name, data_format)
            worksheet.write(row, 2, component.component_code, data_format)
            worksheet.write(row, 3, component.component_name, data_format)
            worksheet.write(row, 4, quote.configuration_code or '', data_format)
            worksheet.write(row, 5, component.article_front_id.code or '', data_format)
            worksheet.write(row, 6, component.article_back_id.code or 'No', data_format)
            worksheet.write(row, 7, component.front_article_qty, data_format)
            worksheet.write(row, 8, component.front_material_cost, money_format)
            worksheet.write(row, 9, component.back_article_qty, data_format)
            worksheet.write(row, 10, component.back_material_cost, money_format)
            worksheet.write(row, 11, component.accessory_qty, data_format)
            # Get options by type
            leg_opt = component.option_ids.filtered(lambda o: o.option_type_id.code == 'LEG')[:1]
            foam_opt = component.option_ids.filtered(lambda o: o.option_type_id.code == 'FOAM')[:1]
            volt_opt = component.option_ids.filtered(lambda o: o.option_type_id.code == 'VOLT')[:1]
            
            worksheet.write(row, 12, foam_opt.name if foam_opt else '', data_format)
            worksheet.write(row, 13, leg_opt.code if leg_opt else '', data_format)
            worksheet.write(row, 14, component.std_fr.upper()[0] if component.std_fr else '', data_format)
            worksheet.write(row, 15, volt_opt.code if volt_opt else '', data_format)
            worksheet.write(row, 16, component.total_cost, money_format)
            worksheet.write(row, 17, quote.create_date.strftime('%d.%m.%Y') if quote.create_date else '', data_format)
            row += 1
        
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        filename = f'Quote_{quote.name}_Component_Summary.xlsx'
        
        return file_data, filename

    def _generate_template3(self):
        """Generate Template 3: Selling Price Export (Price Ratios)"""
        quote = self.quote_id
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Selling Price')
        
        # Formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'center',
        })
        data_format = workbook.add_format({'border': 1})
        money_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        
        # Get all ratios grouped by article type
        fabric_ratios = quote.ratio_ids.filtered(lambda r: r.article_group == 'fabric').sorted('category_id.name')
        leather_ratios = quote.ratio_ids.filtered(lambda r: r.article_group == 'leather').sorted('category_id.name')
        
        # Headers
        headers = ['Image', 'Config', 'SEAT']
        headers += [r.category_name for r in fabric_ratios]
        headers += [r.category_name for r in leather_ratios]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data
        worksheet.write(1, 0, quote.name, data_format)
        worksheet.write(1, 1, quote.configuration_code or '', data_format)
        worksheet.write(1, 2, quote.seat_number, data_format)
        
        col = 3
        for ratio in fabric_ratios:
            worksheet.write(1, col, ratio.selling_price, money_format)
            col += 1
        
        for ratio in leather_ratios:
            worksheet.write(1, col, ratio.selling_price, money_format)
            col += 1
        
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        filename = f'Quote_{quote.name}_Selling_Price.xlsx'
        
        return file_data, filename
