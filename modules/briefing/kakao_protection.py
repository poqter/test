"""Keep the recipient sheet out of the normal Excel UI, preserving macro status writes.

Excel worksheet/structure protection is not encryption; file contents remain
accessible to someone who deliberately inspects the workbook package.
"""
from __future__ import annotations
from copy import deepcopy
from io import BytesIO
import secrets
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
Q = lambda tag: '{' + NS + '}' + tag
ET.register_namespace('', NS)
ET.register_namespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')


def _password_hash(password):
    value = 0
    for char in reversed(password):
        value = ((value >> 14) & 1) | ((value << 1) & 0x7fff)
        value ^= ord(char)
    value = ((value >> 14) & 1) | ((value << 1) & 0x7fff)
    return f'{value ^ len(password) ^ 0xCE4B:04X}'


def hide_and_lock(template):
    with ZipFile(BytesIO(template)) as source:
        parts = {item.filename: (item, source.read(item.filename)) for item in source.infolist()}
    styles = ET.fromstring(parts['xl/styles.xml'][1])
    xfs = styles.find(Q('cellXfs'))
    sheet = ET.fromstring(parts['xl/worksheets/sheet2.xml'][1])
    workbook = ET.fromstring(parts['xl/workbook.xml'][1])
    if xfs is None:
        raise ValueError('엑셀 서식을 확인해 주세요.')
    unlocked = {}
    for cell in sheet.iter(Q('c')):
        address = cell.get('r', '')
        status_cell = address in ('C2', 'C4', 'D4') or (address.startswith('F') and address[1:].isdigit() and 8 <= int(address[1:]) <= 207)
        if status_cell:
            old_style = int(cell.get('s', '0'))
            if old_style not in unlocked:
                new_style = deepcopy(xfs[old_style])
                old_protection = new_style.find(Q('protection'))
                if old_protection is not None:
                    new_style.remove(old_protection)
                new_style.set('applyProtection', '1')
                ET.SubElement(new_style, Q('protection'), {'locked': '0'})
                unlocked[old_style] = len(xfs)
                xfs.append(new_style)
            cell.set('s', str(unlocked[old_style]))
    xfs.set('count', str(len(xfs)))
    sheet_data = sheet.find(Q('sheetData'))
    if sheet_data is None:
        raise ValueError('발송 대상 시트가 올바르지 않습니다.')
    protection = ET.Element(Q('sheetProtection'), {'sheet':'1', 'objects':'0', 'scenarios':'1',
        'formatCells':'0', 'password':_password_hash(secrets.token_hex(7))})
    sheet.insert(list(sheet).index(sheet_data) + 1, protection)
    target = workbook.find(f"{Q('sheets')}/{Q('sheet')}[@name='발송 대상']")
    if target is None:
        raise ValueError('발송 대상 시트를 찾지 못했습니다.')
    target.set('state', 'veryHidden')
    sheets = workbook.find(Q('sheets'))
    workbook.insert(list(workbook).index(sheets), ET.Element(Q('workbookProtection'),
        {'lockStructure':'1', 'workbookPassword':_password_hash(secrets.token_hex(7))}))
    for path, root in [('xl/styles.xml', styles), ('xl/worksheets/sheet2.xml', sheet), ('xl/workbook.xml', workbook)]:
        parts[path] = (parts[path][0], ET.tostring(root, encoding='utf-8', xml_declaration=True))
    out = BytesIO()
    with ZipFile(out, 'w') as result:
        for info, data in parts.values():
            result.writestr(info, data)
    return out.getvalue()
