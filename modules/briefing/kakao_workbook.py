"""Fill the tested macro workbook while preserving its VBA and button parts."""
from __future__ import annotations

from io import BytesIO
from urllib.parse import urlparse
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import re
import unicodedata

from .kakao_recipients import Recipient, assess_recipients
from .kakao_protection import hide_and_lock

_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_XML = 'http://www.w3.org/XML/1998/namespace'
ET.register_namespace('', _NS)
ET.register_namespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')


def _cell(root, address):
    cell = root.find(f'.//{{{_NS}}}c[@r="{address}"]')
    if cell is None:
        raise ValueError('엑셀 서식이 예상과 다릅니다.')
    return cell


def _set_text(root, address, value):
    cell = _cell(root, address)
    for child in list(cell):
        cell.remove(child)
    if not value:
        cell.attrib.pop('t', None)
        return
    cell.set('t', 'inlineStr')
    text = ET.SubElement(ET.SubElement(cell, f'{{{_NS}}}is'), f'{{{_NS}}}t')
    text.set(f'{{{_XML}}}space', 'preserve')
    text.text = value


def _clean_text(value, maximum):
    value = str(value or '').strip()
    if len(value) > maximum or any(unicodedata.category(ch) == 'Cc' and ch not in '\n\r\t' for ch in value):
        raise ValueError('문구에 사용할 수 없는 글자가 있거나 너무 깁니다.')
    return value


def make_workbook(template: bytes, *, day: str, group_name: str, message: str, url: str,
                  recipients: list[Recipient]) -> bytes:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('브리핑 날짜를 확인해 주세요.')
    group_name = _clean_text(group_name, 80)
    message = _clean_text(message, 3000)
    url = _clean_text(url, 2048)
    if not group_name or not message or urlparse(url).scheme != 'https' or not urlparse(url).netloc:
        raise ValueError('그룹, 발송 문구와 공유 링크를 확인해 주세요.')
    if len(recipients) > 200:
        raise ValueError('한 그룹에는 최대 200명까지 등록할 수 있습니다.')
    assessed = assess_recipients(recipients)
    if any(a.state == 'needs_review' for a in assessed):
        raise ValueError('발송 대상의 중복 또는 잘못된 검색 이름을 확인해 주세요.')
    selected = [a.search_name for a in assessed if a.state == 'unverified']
    if not selected:
        raise ValueError('발송할 대상을 한 명 이상 선택해 주세요.')
    source, out = BytesIO(template), BytesIO()
    with ZipFile(source) as zin, ZipFile(out, 'w') as zout:
        if 'xl/vbaProject.bin' not in zin.namelist():
            raise ValueError('매크로 서식이 올바르지 않습니다.')
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in ('xl/worksheets/sheet1.xml', 'xl/worksheets/sheet2.xml'):
                root = ET.fromstring(data)
                if info.filename.endswith('sheet1.xml'):
                    for cell, value in [('B6', '발송 그룹과 인원을 확인하고 카카오톡 발송을 시작하세요.'), ('B9', day), ('E9', group_name), ('B13', message), ('B16', url), ('B24', '발송 대상 명단은 워크스페이스에서 관리합니다.')]:
                        _set_text(root, cell, value)
                    count = _cell(root, 'H9').find(f'{{{_NS}}}v')
                    if count is not None:
                        count.text = f'{len(selected)}명'
                else:
                    for i in range(200):
                        _set_text(root, f'C{i+8}', selected[i] if i < len(selected) else '')
                data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
            zout.writestr(info, data)
    return hide_and_lock(out.getvalue())
