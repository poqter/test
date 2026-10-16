"""Contract ordering and upload-scoped UI state."""
import copy
import hashlib
import re
from datetime import date


def sort_contracts(data):
    result = copy.deepcopy(data)
    def key(index):
        contract = result['contracts'][index]
        value = str(contract.get('start') or contract.get('coverage_period') or '')
        match = re.match(r'\s*(\d{4})\D?(\d{2})\D?(\d{2})', value)
        try:
            ordinal = date(*map(int, match.groups())).toordinal() if match else 0
        except ValueError:
            ordinal = 0
        return -ordinal
    order = sorted(range(len(result['contracts'])), key=key)
    result['contracts'] = [result['contracts'][i] for i in order]
    for item in result['coverages']:
        item['values'] = [item['values'][i] for i in order]
    mapping = {old:new for new,old in enumerate(order)}
    for record in result.get('details', []):
        record['contract'] = mapping[record['contract']]
    return result


def reset_for_upload(state, content):
    token = hashlib.sha256(content).hexdigest() if content else None
    if state.get('analyzer_active_upload') != token:
        for key in list(state):
            if key.startswith(('kb_', 'analyzer_v2_cov_')) or key in (
                'analyzer_v2_result','analyzer_v2_error','analyzer_kb_unlock','analyzer_kb_password'):
                state.pop(key, None)
        state['analyzer_active_upload'] = token


def result_is_current(result, signature):
    return bool(signature and result and result.get('signature') == signature)
