"""Synthetic local-only PDF editor browser regression; no customer documents."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import io
import os
import random
import zipfile
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def run():
    with TemporaryDirectory() as directory:
        fixtures = Path(directory)
        doc = canvas.Canvas(str(fixtures / 'proposal.pdf'))
        for i in range(3):
            doc.drawString(50, 700, f'PAGE {i+1} / synthetic claim document')
            doc.showPage()
        doc.save()
        im = Image.new('RGB', (600, 800), '#353b43')
        draw = ImageDraw.Draw(im)
        draw.polygon([(80,90),(520,55),(550,730),(50,700)], fill='white')
        for y in range(150,650,30):
            draw.line([(140,y),(420,y)], fill='black', width=3)
        im.save(fixtures/'photo.jpg', quality=95)
        (fixtures/'broken.pdf').write_bytes(b'%PDF broken')
        noisy = Image.frombytes('RGB', (1400,1800), random.Random(42).randbytes(1400*1800*3))
        noisy.save(fixtures/'scan.jpg', quality=98)
        root = ROOT/'modules/resources/pdf_tools'
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(root)))
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser_type=getattr(pw, os.getenv('PDF_TEST_BROWSER', 'chromium'))
                kwargs={'headless': True}
                if os.getenv('PDF_TEST_EXECUTABLE'):
                    kwargs['executable_path']=os.environ['PDF_TEST_EXECUTABLE']
                browser=browser_type.launch(**kwargs)
                page=browser.new_page(viewport={'width':1360,'height':1000})
                errors=[]
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('dialog', lambda dialog: dialog.accept())
                page.goto(f'http://127.0.0.1:{server.server_port}')
                def idle():
                    page.wait_for_function("document.querySelector('#busy').hidden", timeout=120000)
                def generate():
                    page.locator('#generate').click()
                    page.locator('#review').wait_for(state='visible', timeout=120000)
                    idle()
                page.locator('#files').set_input_files([str(fixtures/name) for name in ['proposal.pdf','photo.jpg','broken.pdf']])
                idle()
                assert page.locator('#pages .card').count()==4
                assert 'broken' in page.locator('#errors').inner_text()
                page.locator('#files').set_input_files(str(fixtures/'proposal.pdf'))
                page.locator('#duplicateSkip').click()
                idle()
                assert page.locator('#pages .card').count()==4
                page.locator('#range').fill('1-2')
                page.locator('#selectRange').click()
                assert page.locator('.marked').count()==2
                assert '저장할 페이지 4쪽' in page.locator('#count').inner_text()
                page.locator('#batchExclude').click()
                assert page.locator('.off').count()==2
                page.locator('#undo').click()
                page.locator('#batchBack').click()
                assert '원본 3쪽' in page.locator('#pages .card').first.inner_text()
                page.locator('#undo').click()
                page.locator('#groupName').fill('청구서')
                page.locator('#batchGroup').click()
                photo=page.locator('#pages .card').filter(has_text='photo.jpg')
                photo.get_by_role('button',name='사진 보정',exact=True).click()
                page.wait_for_function("!document.querySelector('#photoApply').disabled")
                assert '테두리를 제안' in page.locator('#photoStatus').inner_text()
                page.locator('#photoBrightness').fill('10')
                page.wait_for_function("!document.querySelector('#photoApply').disabled")
                page.locator('#photoApply').click()
                assert '적용됨' in photo.inner_text()
                page.locator('#undo').click()
                assert '적용됨' not in photo.inner_text()
                page.locator('#redo').click()
                page.locator('#mode').select_option('groups')
                generate()
                assert page.locator('.result').count()==2
                with page.expect_download() as download:
                    page.locator('#download').click()
                with zipfile.ZipFile(download.value.path()) as archive:
                    readers=[PdfReader(io.BytesIO(archive.read(name))) for name in archive.namelist()]
                    assert [len(reader.pages) for reader in readers]==[2,2]
                    assert '청구서' in archive.namelist()[0]
                    # The photo is rectified to the measured document rectangle.
                    corrected=readers[1].pages[1]
                    ratio=float(corrected.mediabox.width)/float(corrected.mediabox.height)
                    assert .65 < ratio < .8
                assert '요청했습니다' in page.locator('#downloadStatus').inner_text()
                page.locator('#reviewPages .card').first.get_by_role('button',name='화질 비교').click()
                page.locator('#viewNext').click()
                assert '2 / 2' in page.locator('#viewPosition').inner_text()
                page.locator('#closeView').click()
                page.locator('#back').click()
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                photo.get_by_role('button',name='사진 보정 · 적용됨').click()
                page.wait_for_function("!document.querySelector('#photoApply').disabled")
                assert page.evaluate("document.querySelector('#photoDialog').scrollWidth<=document.querySelector('#photoDialog').clientWidth")
                page.locator('#photoClose').click()
                page.locator('#reset').click()
                page.locator('#files').set_input_files([str(fixtures/'scan.jpg'),str(fixtures/'proposal.pdf')])
                idle()
                page.locator('#mode').select_option('size')
                page.locator('#target').select_option('custom')
                page.locator('#custom').fill('0.1')
                generate()
                assert page.locator('.result').count() >= 2
                assert '한 페이지가 목표' in page.locator('#results').inner_text()
                with page.expect_download() as download:
                    page.locator('#download').click()
                with zipfile.ZipFile(download.value.path()) as archive:
                    assert sum(len(PdfReader(io.BytesIO(archive.read(n))).pages) for n in archive.namelist())==4
                assert not errors, errors
                browser.close()
                print('PASS PDF editing, photo detection/rectification, duplicates, partial errors, groups, split, ZIP, mobile')
        finally:
            server.shutdown()


if __name__=='__main__':
    run()
