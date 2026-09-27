"""Validate the workbook/sheet relationship graph before business parsing."""
import posixpath
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
DOC = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
WORKBOOK_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'
SHEET_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'


def _target(base, value):
    value = unquote(value or '')
    if not value or '\\' in value or urlsplit(value).scheme or urlsplit(value).netloc:
        raise ValueError('관계 대상 형식 오류')
    result = posixpath.normpath(value.lstrip('/') if value.startswith('/') else posixpath.join(base, value))
    if result.startswith('../') or result in ('.', '..') or '?' in result or '#' in result:
        raise ValueError('관계 대상 경로 오류')
    return result


def _xml(archive, name, root):
    element = ET.fromstring(archive.read(name))
    if element.tag != root:
        raise ValueError('Excel XML 루트 형식 오류')
    return element


def validate_structure(archive):
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError('중복된 내부 파일')
    types = _xml(archive, '[Content_Types].xml', '{'+CT+'}Types')
    overrides = {n.get('PartName','').lstrip('/'):n.get('ContentType') for n in types.findall('{'+CT+'}Override')}
    if overrides.get('xl/workbook.xml') != WORKBOOK_TYPE:
        raise ValueError('지원하는 XLSX 통합문서가 아닙니다.')
    roots = _xml(archive, '_rels/.rels', '{'+REL+'}Relationships')
    books = [n for n in roots if n.get('Type') == DOC+'/officeDocument']
    if len(books) != 1 or books[0].get('TargetMode') == 'External' or _target('',books[0].get('Target')) != 'xl/workbook.xml':
        raise ValueError('통합문서 연결 오류')
    book = _xml(archive, 'xl/workbook.xml', '{'+MAIN+'}workbook')
    relations = _xml(archive, 'xl/_rels/workbook.xml.rels', '{'+REL+'}Relationships')
    links = {}
    for relation in relations:
        identity = relation.get('Id')
        if not identity or identity in links:
            raise ValueError('통합문서 관계 ID 오류')
        links[identity] = relation
    sheets = book.findall('{'+MAIN+'}sheets/{'+MAIN+'}sheet')
    if not sheets:
        raise ValueError('통합문서에 시트가 없습니다.')
    worksheets = set()
    seen = set()
    for sheet in sheets:
        identity = sheet.get('{'+DOC+'}id')
        relation = links.get(identity)
        if relation is None or identity in seen or relation.get('TargetMode') == 'External':
            raise ValueError('시트 연결 오류')
        seen.add(identity)
        target = _target('xl', relation.get('Target'))
        if target not in names:
            raise ValueError('연결된 시트 파일이 없습니다.')
        kind = relation.get('Type')
        if kind == DOC+'/worksheet':
            if overrides.get(target) != SHEET_TYPE:
                raise ValueError('워크시트 형식 오류')
            worksheets.add(target)
        elif kind != DOC+'/chartsheet':
            raise ValueError('지원하지 않는 시트 연결')
    if not worksheets:
        raise ValueError('읽을 수 있는 워크시트가 없습니다.')
    return worksheets
