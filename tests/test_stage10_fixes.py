import io
import unittest
import zipfile
from unittest.mock import patch
from datetime import date
from openpyxl import load_workbook
from pypdf import PdfWriter
from modules.remodeling import Person,NewPlan,create_excel
from modules.validators import validate_upload,ValidationError
from modules.upload_ui import other_upload_bytes
from streamlit.runtime.uploaded_file_manager import UploadedFile,UploadedFileRec
from streamlit.proto.Common_pb2 import FileURLs
from fixture_factory import synthetic_xlsx
from test_signature import opened

class Stage10Tests(unittest.TestCase):
    def test_literal_plan_name(self):
        p=Person('가상',100,200,30,60,[NewPlan('=2+2',20,20,120)])
        wb=load_workbook(create_excel([p],'가상 검사',date(2026,9,23),'가상'))
        c=wb['리모델링 비교안']['K10']
        self.assertEqual(c.value,'=2+2');self.assertEqual(c.data_type,'s')

    def test_non_workbook_zip_rejected(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('other.txt','synthetic')
        with self.assertRaises(ValidationError):validate_upload('a.xlsx',b.getvalue())
        validate_upload('a.xlsx',synthetic_xlsx())

    def test_pdf_page_limit(self):
        writer=PdfWriter()
        writer.add_blank_page(width=100,height=100)
        b=io.BytesIO();writer.write(b);validate_upload('a.pdf',b.getvalue())
        for _ in range(100):writer.add_blank_page(width=100,height=100)
        b=io.BytesIO();writer.write(b)
        with self.assertRaises(ValidationError):validate_upload('a.pdf',b.getvalue())

    def test_upload_count_replace_and_dedup(self):
        def file(identity,size):return UploadedFile(UploadedFileRec(identity,'a.xlsx','application/octet-stream',b'x'*size),FileURLs())
        a=file('a',10);b=file('b',20)
        self.assertEqual(other_upload_bytes(a,[a,b,b]),20)
        self.assertEqual(other_upload_bytes(b,[a,b]),10)
        self.assertEqual(other_upload_bytes(a,[a,None]),0)
        with self.assertRaises(ValidationError):validate_upload('a.xlsx',synthetic_xlsx(),session_total=60*1024*1024)

    def test_parser_error_redacted(self):
        u=io.BytesIO(synthetic_xlsx());u.name='synthetic.xlsx'
        with patch('modules.upload_ui.st.file_uploader',return_value=u),patch('modules.manager_results.load_df_from_bytes',side_effect=ValueError('SYNTHETIC_MARKER')):
            at=opened('manager_results')
            self.assertFalse(at.exception)
            self.assertTrue(at.error)
            self.assertFalse(any('SYNTHETIC_MARKER' in e.value for e in at.error))

    def test_home_and_material_labels(self):
        for page in ['home','consultation_helper','comparison_builder','customer_materials']:
            at=opened(page)
            self.assertFalse(at.exception)
            for element in [*at.markdown,*at.caption,*at.text_input,*at.text_area,*at.button,*at.expander]:
                rendered=str(getattr(element,'value',''))+' '+str(getattr(element,'label',''))
                self.assertNotIn('개인정보',rendered)
                self.assertNotIn('서버 메모리',rendered)
