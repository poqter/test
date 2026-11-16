import io
from pathlib import Path
import sys
import unittest
import types
import importlib.util
from xml.etree import ElementTree as ET
from zipfile import ZipFile

MODULE_DIR = Path(__file__).resolve().parents[1] / 'modules' / 'briefing'
package = types.ModuleType('_kakao_test')
package.__path__ = [str(MODULE_DIR)]
sys.modules[package.__name__] = package
for name in ('kakao_recipients', 'kakao_protection', 'kakao_workbook'):
    spec = importlib.util.spec_from_file_location('_kakao_test.' + name, MODULE_DIR / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
Recipient = sys.modules['_kakao_test.kakao_recipients'].Recipient
make_workbook = sys.modules['_kakao_test.kakao_workbook'].make_workbook

TEMPLATE = Path(__file__).resolve().parents[2] / 'outputs/kakao_excel/hwarang_briefing_kakao_test.xlsm'
NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

class WorkbookTest(unittest.TestCase):
    def setUp(self):
        if TEMPLATE.exists():
            self.template = TEMPLATE.read_bytes()
        else:
            self.template = self.synthetic_template()
        self.data = dict(day='2026-10-30', group_name='고객 & 친구', message='오늘 소식\n안내',
                         url='https://example.com/?a=1&b=2',
                         recipients=[Recipient('첫째', '홍길동 고객'), Recipient('둘째', '=수식아님')])

    @staticmethod
    def synthetic_template():
        root_ns = NS['x']
        q = lambda n: '{' + root_ns + '}' + n
        def c(row, addr, text=None, formula=None):
            cell = ET.SubElement(row, q('c'), {'r': addr, 's': '0'})
            if formula is not None: ET.SubElement(cell, q('f')).text = formula
            if text is not None: ET.SubElement(cell, q('v')).text = text
        def sheet(addresses):
            root = ET.Element(q('worksheet'))
            sd = ET.SubElement(root, q('sheetData'))
            for i, addr in enumerate(addresses):
                row = ET.SubElement(sd, q('row'), {'r': str(i + 1)})
                c(row, addr, '0명' if addr == 'H9' else None, '1' if addr in ('H9', 'D8') else None)
            return ET.tostring(root)
        work = ET.Element(q('workbook'))
        sheets = ET.SubElement(work, q('sheets'))
        ET.SubElement(sheets, q('sheet'), {'name': '발송 화면', 'sheetId':'1'})
        ET.SubElement(sheets, q('sheet'), {'name': '발송 대상', 'sheetId':'2'})
        styles = ET.Element(q('styleSheet'))
        xfs = ET.SubElement(styles, q('cellXfs'), {'count':'1'})
        ET.SubElement(xfs, q('xf'))
        out = io.BytesIO()
        with ZipFile(out, 'w') as z:
            for path, data in {
                'xl/workbook.xml':ET.tostring(work), 'xl/styles.xml':ET.tostring(styles),
                'xl/worksheets/sheet1.xml':sheet(['B6','B9','E9','B13','B16','B24','H9']),
                'xl/worksheets/sheet2.xml':sheet(['C2','C4','D4','D8'] + [f'C{i}' for i in range(8,208)] + [f'F{i}' for i in range(8,208)]),
                'xl/vbaProject.bin':b'test-macro', 'xl/drawings/drawing1.xml':b'test-button',
                'xl/worksheets/_rels/sheet1.xml.rels':b'test-rels',
            }.items(): z.writestr(path,data)
        return out.getvalue()

    def test_macro_and_button_are_identical_and_values_are_safe(self):
        result = make_workbook(self.template, **self.data)
        with ZipFile(io.BytesIO(self.template)) as original, ZipFile(io.BytesIO(result)) as actual:
            for name in ('xl/vbaProject.bin', 'xl/drawings/drawing1.xml', 'xl/worksheets/_rels/sheet1.xml.rels'):
                self.assertEqual(original.read(name), actual.read(name))
            a = ET.fromstring(actual.read('xl/worksheets/sheet1.xml'))
            b = ET.fromstring(actual.read('xl/worksheets/sheet2.xml'))
            def value(root, address):
                c = root.find(f'.//x:c[@r="{address}"]', NS)
                return c, c.findtext('x:is/x:t', default='', namespaces=NS)
            w = ET.fromstring(actual.read('xl/workbook.xml'))
            self.assertEqual(w.find("x:sheets/x:sheet[@name='발송 대상']", NS).get('state'), 'veryHidden')
            self.assertEqual(w.find('x:workbookProtection', NS).get('lockStructure'), '1')
            self.assertEqual(b.find('x:sheetProtection', NS).get('sheet'), '1')
            self.assertEqual(value(a, 'B16')[1], self.data['url'])
            self.assertEqual(value(a, 'E9')[1], self.data['group_name'])
            self.assertEqual(value(b, 'C8')[1], '홍길동 고객')
            c, v = value(b, 'C9')
            self.assertEqual((c.get('t'), v), ('inlineStr', '=수식아님'))
            self.assertIsNone(value(b, 'C10')[0].get('t'))
            self.assertEqual(a.find('.//x:c[@r="H9"]/x:v', NS).text, '2명')
            self.assertIsNotNone(b.find('.//x:c[@r="D8"]/x:f', NS))

    def test_duplicate_and_empty_lists_refused(self):
        for people in ([], [Recipient('a', '같음'), Recipient('b', '같음')]):
            with self.assertRaises(ValueError):
                make_workbook(self.template, **{**self.data, 'recipients': people})

    def test_limit_and_bad_url(self):
        with self.assertRaises(ValueError):
            make_workbook(self.template, **{**self.data, 'url': 'javascript:alert(1)'})
        with self.assertRaises(ValueError):
            make_workbook(self.template, **{**self.data, 'recipients': [Recipient(str(i), str(i)) for i in range(201)]})

if __name__ == '__main__': unittest.main()
